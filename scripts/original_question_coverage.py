#!/usr/bin/env python3
"""Build the 307-question coverage ledger and select unseen originals.

Knowledge mapping, answer readiness, scheduling and actual learner exposure are
deliberately separate states.  This script never changes answer, attempt or
mastery records; it derives a reproducible view from their source files.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "knowledge_base" / "article_map" / "question_map.json"
ATTEMPTS_PATH = ROOT / "10-逐题作答记录.csv"
DB_PATH = ROOT / "knowledge_base" / "cippe_kb.sqlite3"
JSON_OUTPUT = ROOT / "knowledge_base" / "original_question_coverage.json"
MD_OUTPUT = ROOT / "knowledge_base" / "original_question_coverage.md"
AUDIT_QUEUE_OUTPUT = ROOT / "knowledge_base" / "article_map" / "待审核题按规则分组.md"

EXACT_ORIGINAL = re.compile(r"^TQ-(\d{3})$")


def matches_article(reference: str, request: str) -> bool:
    """Match a GDPR Article number without confusing 3 with 30/33/35."""
    match = re.fullmatch(r"(?:GDPR\s*)?(\d+)", request.strip(), re.IGNORECASE)
    if not match:
        return request.casefold() in reference.casefold()
    wanted = int(match.group(1))
    for scope in re.findall(r"(?:EU\s+)?GDPR\s*([0-9(),\s–—\-]+)", reference, re.IGNORECASE):
        scope = re.sub(r"\([^)]*\)", "", scope)
        for low, high in re.findall(r"(\d+)(?:\s*[–—-]\s*(\d+))?", scope):
            if int(low) <= wanted <= int(high or low):
                return True
    return False


def exact_original_attempts(path: Path = ATTEMPTS_PATH) -> dict[int, list[dict[str, str]]]:
    attempts: dict[int, list[dict[str, str]]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            match = EXACT_ORIGINAL.fullmatch((row.get("question_id") or "").strip())
            if not match:
                continue
            # Guided repairs and variants must never masquerade as original exposure.
            if row.get("source_type") != "user_pdf_original" or row.get("mode") != "original":
                continue
            attempts.setdefault(int(match.group(1)), []).append(row)
    return attempts


def database_metadata(path: Path = DB_PATH) -> tuple[dict[int, dict[str, object]], dict[int, list[dict[str, str]]]]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    questions = {
        row["q_no"]: dict(row)
        for row in connection.execute(
            """SELECT q.q_no, q.verification_status, q.verified_on,
                      EXISTS(SELECT 1 FROM question_audits a WHERE a.q_no=q.q_no) AS has_audit
                 FROM questions q ORDER BY q.q_no"""
        )
    }
    links: dict[int, list[dict[str, str]]] = {}
    for row in connection.execute(
        """SELECT l.q_no, l.indicator_id, l.role,
                  COALESCE(r.planned_session, '') AS planned_session,
                  COALESCE(r.status, '') AS route_status
             FROM question_indicator_links l
             LEFT JOIN indicator_routes r ON r.indicator_id=l.indicator_id
             ORDER BY l.q_no, CASE l.role WHEN 'main' THEN 0 ELSE 1 END, l.indicator_id"""
    ):
        links.setdefault(row["q_no"], []).append(dict(row))
    connection.close()
    return questions, links


def build_inventory(root: Path = ROOT) -> dict[str, object]:
    mapping_path = root / MAP_PATH.relative_to(ROOT)
    attempts_path = root / ATTEMPTS_PATH.relative_to(ROOT)
    db_path = root / DB_PATH.relative_to(ROOT)
    mappings = json.loads(mapping_path.read_text(encoding="utf-8"))
    concepts = json.loads(
        (root / "knowledge_base" / "article_map" / "concepts.json").read_text(encoding="utf-8")
    )
    attempts = exact_original_attempts(attempts_path)
    db_questions, indicator_links = database_metadata(db_path)
    rows: list[dict[str, object]] = []

    for item in mappings:
        q_no = int(item["q_no"])
        db = db_questions[q_no]
        q_attempts = attempts.get(q_no, [])
        blocked = (
            item.get("answer_status") == "blocked_missing_question"
            or item.get("mapping_status") != "mapped"
            or db["verification_status"] in {"needs_review", "outdated"}
        )
        answer_ready = bool(
            db["verification_status"] == "verified" and db["has_audit"] and not blocked
        )
        if q_attempts:
            coverage_status = "attempted"
        elif blocked:
            coverage_status = "blocked"
        elif answer_ready:
            coverage_status = "ready_unseen"
        else:
            coverage_status = "needs_audit"

        rows.append(
            {
                "q_no": q_no,
                "question_id": f"TQ-{q_no:03d}",
                "task": item.get("task", ""),
                "mapping_status": item.get("mapping_status", ""),
                "answer_status": item.get("answer_status", ""),
                "verification_status": db["verification_status"],
                "has_audit": bool(db["has_audit"]),
                "answer_ready": answer_ready,
                "coverage_status": coverage_status,
                "attempt_count": len(q_attempts),
                "first_attempt": min((row["date"] for row in q_attempts), default=None),
                "last_attempt": max((row["date"] for row in q_attempts), default=None),
                "main_concepts": item.get("main_concepts", []),
                "associated_concepts": item.get("associated_concepts", []),
                "primary_rules": [
                    {
                        "concept_id": concept_id,
                        "concept": concepts[concept_id]["concept"],
                        "article": concepts[concept_id]["article"],
                    }
                    for concept_id in item.get("main_concepts", [])
                ],
                "secondary_rules": [
                    {
                        "concept_id": concept_id,
                        "concept": concepts[concept_id]["concept"],
                        "article": concepts[concept_id]["article"],
                    }
                    for concept_id in item.get("associated_concepts", [])
                ],
                "textbook_sections": item.get("textbook_sections", []),
                "indicators": indicator_links.get(q_no, []),
                "warning": item.get("warning", ""),
            }
        )

    if len(rows) != 307 or {row["q_no"] for row in rows} != set(range(1, 308)):
        raise ValueError("Coverage ledger requires exactly TQ-001 through TQ-307")
    counts = Counter(str(row["coverage_status"]) for row in rows)
    summary = {
        "total": len(rows),
        "attempted": counts["attempted"],
        "ready_unseen": counts["ready_unseen"],
        "needs_audit": counts["needs_audit"],
        "blocked": counts["blocked"],
        "original_coverage_percent": round(counts["attempted"] / len(rows) * 100, 1),
    }
    return {"generated_on": date.today().isoformat(), "summary": summary, "questions": rows}


def select_candidates(
    inventory: dict[str, object], *, bok: str | None = None,
    concept: str | None = None, article: str | None = None, limit: int = 5,
) -> list[dict[str, object]]:
    candidates = []
    for row in inventory["questions"]:  # type: ignore[index]
        if row["coverage_status"] != "ready_unseen":
            continue
        if concept and concept not in row["main_concepts"] and concept not in row["associated_concepts"]:
            continue
        if article and not any(matches_article(rule["article"], article) for rule in row["primary_rules"]):
            continue
        matching_links = [link for link in row["indicators"] if not bok or link["indicator_id"].startswith(bok)]
        if bok and not matching_links:
            continue
        main_match = any(link["role"] == "main" for link in matching_links)
        # Main BoK links first, then questions with a warning last, then source order.
        priority = (0 if main_match else 1, 1 if row["warning"] else 0, row["q_no"])
        candidates.append((priority, row))
    return [row for _, row in sorted(candidates, key=lambda item: item[0])[:limit]]


def article_summary(inventory: dict[str, object], article: str) -> dict[str, object]:
    primary = [
        row for row in inventory["questions"]
        if any(matches_article(rule["article"], article) for rule in row["primary_rules"])
    ]
    primary_ids = {row["q_no"] for row in primary}
    related = [
        row for row in inventory["questions"]
        if row["q_no"] not in primary_ids
        and any(matches_article(rule["article"], article) for rule in row["secondary_rules"])
    ]
    counts = Counter(row["coverage_status"] for row in primary)
    return {
        "article": f"GDPR Article {int(re.sub(r'\D', '', article))}" if re.fullmatch(r"(?:GDPR\s*)?\d+", article, re.IGNORECASE) else article,
        "primary_total": len(primary),
        "attempted": counts["attempted"],
        "ready_unseen": counts["ready_unseen"],
        "needs_audit": counts["needs_audit"],
        "blocked": counts["blocked"],
        "related_only": len(related),
    }


def render_markdown(inventory: dict[str, object]) -> str:
    summary = inventory["summary"]
    lines = [
        "# CIPP/E 307题原题覆盖账本", "",
        "> 本页由 `scripts/original_question_coverage.py` 生成。“知识点已学”不等于“原题已作答”；变式、引导修复和 side chat 不计为原题覆盖。", "",
        "## 当前概览", "",
        f"- 真实作答过的原题：**{summary['attempted']} / {summary['total']}（{summary['original_coverage_percent']}%）**",
        f"- 已核验、可优先调度但尚未作答：**{summary['ready_unseen']}**",
        f"- 需先完成答案审核：**{summary['needs_audit']}**",
        f"- 因缺题干、歧义、过时等暂停：**{summary['blocked']}**", "",
        "## 状态定义", "",
        "`attempted` = 逐题记录中存在精确 `TQ-NNN + user_pdf_original + original` 作答；`ready_unseen` = 已完成语义审核但未作答；`needs_audit` = 映射完成但答案尚未审核；`blocked` = 暂不应用于判分。", "",
        "## 逐题账本", "",
        "| 原题 | 判断任务 | 状态 | 作答次数 | 主规则入口 | 主 BoK | 提醒 |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for row in inventory["questions"]:
        main_bok = ", ".join(link["indicator_id"] for link in row["indicators"] if link["role"] == "main") or "—"
        concepts = "<br>".join(
            f"{rule['article']} · {rule['concept']} (`{rule['concept_id']}`)"
            for rule in row["primary_rules"]
        ) or "—"
        warning = str(row["warning"]).replace("|", "\\|") or "—"
        task = str(row["task"]).replace("|", "\\|")
        lines.append(
            f"| {row['question_id']} | {task} | `{row['coverage_status']}` | "
            f"{row['attempt_count']} | {concepts} | {main_bok} | {warning} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_audit_queue(inventory: dict[str, object]) -> str:
    """Render the unresolved answer audit as primary-rule work packets."""
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for row in inventory["questions"]:
        if row["coverage_status"] != "needs_audit":
            continue
        for rule in row["primary_rules"]:
            key = (rule["article"], rule["concept"], rule["concept_id"])
            groups.setdefault(key, []).append(row)

    unique_questions = {
        row["q_no"] for rows in groups.values() for row in rows
    }
    if len(unique_questions) != inventory["summary"]["needs_audit"]:
        raise ValueError("Every needs_audit question must appear in a primary rule group")

    lines = [
        "# 待审核原题：按 Article／规则分组", "",
        "> 本页是教师侧工作队列，由原题覆盖脚本自动生成。题目在这里“已挂载”只代表存在语义路由，不代表答案已核验或学习者已掌握。", "",
        f"- 待审核独立原题：**{len(unique_questions)}**",
        f"- 主规则工作包：**{len(groups)}**",
        "- 一道综合题可同时出现在多个主规则包中；总数仍按独立题号计算。", "",
        "## 审核准入条件", "",
        "每题必须核对完整题干和 A–D、实际读取列出的教材正文、核对必要的官方现行来源，并确认唯一最佳答案。完成前不进入 `ready_unseen`。", "",
    ]
    for (article, concept, concept_id), rows in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])):
        lines.extend([
            f"## {article} — {concept}", "",
            f"> 概念 ID：`{concept_id}`；待审核：{len(rows)} 题。", "",
            "| 原题 | 判断任务 | 教材入口 | 交叉规则 | 提醒 |",
            "|---|---|---|---|---|",
        ])
        for row in sorted(rows, key=lambda item: item["q_no"]):
            sections = ", ".join(f"§{section}" for section in row["textbook_sections"]) or "—"
            secondary = "<br>".join(
                f"{rule['article']} · {rule['concept']}"
                for rule in row["secondary_rules"]
            ) or "—"
            warning = str(row["warning"]).replace("|", "\\|") or "—"
            task = str(row["task"]).replace("|", "\\|")
            lines.append(
                f"| {row['question_id']} | {task} | {sections} | {secondary} | {warning} |"
            )
        lines.append("")
    return "\n".join(lines)


def write_outputs(inventory: dict[str, object], root: Path = ROOT) -> None:
    json_output = root / JSON_OUTPUT.relative_to(ROOT)
    md_output = root / MD_OUTPUT.relative_to(ROOT)
    audit_queue_output = root / AUDIT_QUEUE_OUTPUT.relative_to(ROOT)
    json_output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_output.write_text(render_markdown(inventory), encoding="utf-8")
    audit_queue_output.write_text(render_audit_queue(inventory), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and query exact original-question coverage")
    parser.add_argument("--bok", help="Select ready unseen originals linked to this BoK prefix, e.g. III.D")
    parser.add_argument("--concept", help="Select ready unseen originals linked to this concept id")
    parser.add_argument(
        "--article", action="append",
        help="Show counts for an Article; repeat for a multi-Article opening card",
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--select", action="store_true", help="Print a teacher-only candidate list")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    inventory = build_inventory()
    write_outputs(inventory)
    summary = inventory["summary"]
    print(
        f"ORIGINAL COVERAGE: {summary['attempted']}/{summary['total']} "
        f"({summary['original_coverage_percent']}%); ready_unseen={summary['ready_unseen']}; "
        f"needs_audit={summary['needs_audit']}; blocked={summary['blocked']}"
    )
    if args.select:
        selected = select_candidates(
            inventory, bok=args.bok, concept=args.concept,
            article=args.article[0] if args.article and len(args.article) == 1 else None,
            limit=args.limit,
        )
        print(json.dumps({"teacher_only": True, "candidates": selected}, ensure_ascii=False, indent=2))
    if args.article:
        print(json.dumps(
            {"article_opening_card": [article_summary(inventory, value) for value in args.article]},
            ensure_ascii=False, indent=2,
        ))


if __name__ == "__main__":
    main()
