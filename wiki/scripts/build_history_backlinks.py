#!/usr/bin/env python3
"""Build historical learning indexes and backlink them from existing rule pages."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from audit_history_coverage import legal_refs
from build_object_index import frontmatter, list_values, scalar


ROOT = Path(__file__).resolve().parents[2]
WIKI = ROOT / "wiki"
START = "<!-- HISTORY-BACKLINKS:START -->"
END = "<!-- HISTORY-BACKLINKS:END -->"


def write_if_changed(path: Path, content: str) -> bool:
    normalized = content.rstrip() + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == normalized:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized, encoding="utf-8")
    return True


def rules() -> dict[str, set[str]]:
    result = {}
    for path in sorted((WIKI / "rules").glob("*.md")):
        meta = frontmatter(path)
        if meta is None or scalar(meta, "type") != "rule":
            continue
        title = scalar(meta, "title") or path.stem
        aliases = " ".join(list_values(meta, "ref_aliases"))
        result[path.stem] = legal_refs(f"{path.stem} {title} {aliases}")
    return result


def matched_rules(raw: str, inventory: dict[str, set[str]]) -> list[str]:
    numbers = legal_refs(raw)
    return [stem for stem, present in inventory.items() if numbers & present]


def load_wrong_rows() -> list[dict[str, str]]:
    with (ROOT / "10-逐题作答记录.csv").open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("correct", "").lower() == "false"]


def event_records(inventory: dict[str, set[str]]) -> list[dict]:
    records = []
    for path in sorted((WIKI / "learning-events").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta = frontmatter(path) or ""
        links = set(re.findall(r"\[\[([^\]|#]+)", text))
        records.append({
            "stem": path.stem,
            "title": scalar(meta, "title") or path.stem.removeprefix("LE-"),
            "rules": sorted(links & inventory.keys()),
        })
    return records


def render_wrong_index(rows: list[dict[str, str]], inventory: dict[str, set[str]]) -> str:
    sections = []
    for row in rows:
        links = matched_rules(row.get("rule", ""), inventory)
        linked = "、".join(f"[[{stem}]]" for stem in links) or "待建立或审核规则关系"
        sections.append(
            f"## {row['question_id']} · {row['date']}\n\n"
            f"- 规则标签：`{row.get('rule') or '未记录'}`\n"
            f"- 错因代码：`{row.get('error_code') or '未记录'}`\n"
            f"- 作答模式：`{row.get('mode') or '未记录'}`\n"
            f"- 信心：`{row.get('confidence') or '未报告'}`\n"
            f"- 已有规则入口：{linked}\n"
            f"- 当时记录：{row.get('notes') or '未记录'}"
        )
    return (
        "---\n"
        "type: index\n"
        "id: INDEX-HISTORICAL-WRONG-QUESTIONS\n"
        'title: "历史明确错题索引"\n'
        "generated: true\n"
        "generated_on: 2026-09-13\n"
        "authority_status: personal_learning_evidence\n"
        "source_refs:\n"
        '  - "10-逐题作答记录.csv"\n'
        "---\n\n"
        "# 历史明确错题索引\n\n"
        "> 本页只投影明确记录为错误的学习事件；不改变原始答案、核验或掌握状态。\n\n"
        + "\n\n".join(sections)
        + "\n"
    )


def render_event_index(records: list[dict]) -> str:
    lines = []
    for record in records:
        linked = "、".join(f"[[{stem}]]" for stem in record["rules"]) or "无正式规则页链接"
        lines.append(f"- [[{record['stem']}|{record['title']}]] → {linked}")
    return (
        "---\n"
        "type: index\n"
        "id: INDEX-CONVERSATION-LEARNING-EVENTS\n"
        'title: "对话与学习事件索引"\n'
        "generated: true\n"
        "generated_on: 2026-09-13\n"
        "authority_status: personal_learning_evidence\n"
        "source_refs:\n"
        '  - "wiki/learning-events/"\n'
        "---\n\n"
        "# 对话与学习事件索引\n\n"
        "> 事件页不可变；这里仅提供从事件到已有规则的导航。\n\n"
        + "\n".join(lines)
        + "\n"
    )


def backlink_block(rule: str, wrong: list[dict], events: list[dict]) -> str:
    wrong_lines = [
        f"- [[WRONG-QUESTIONS#{row['question_id']} · {row['date']}|{row['question_id']} · {row['date']}]]"
        for row in wrong if rule in row["rules"]
    ]
    event_lines = [f"- [[{item['stem']}|{item['title']}]]" for item in events if rule in item["rules"]]
    wrong_count = len(wrong_lines)
    event_count = len(event_lines)
    lines = [START, "", f"> [!example]- 我的历史学习证据（错题 {wrong_count} · 事件 {event_count}）", ">"]
    lines.extend(["> **明确答错记录**", ">", *[f"> {line}" for line in (wrong_lines or ["- 暂无明确答错记录。"])], ">"])
    lines.extend(["> **对话与学习事件**", ">", *[f"> {line}" for line in (event_lines or ["- 暂无已投影事件。"])], "", END])
    return "\n".join(lines)


def update_rule(path: Path, block: str) -> bool:
    text = path.read_text(encoding="utf-8").rstrip()
    if START in text and END in text:
        updated = re.sub(re.escape(START) + r".*?" + re.escape(END), block, text, flags=re.DOTALL)
    else:
        updated = f"{text}\n\n{block}"
    return write_if_changed(path, updated)


def build() -> dict:
    inventory = rules()
    raw_wrong = load_wrong_rows()
    wrong = [dict(row, rules=matched_rules(row.get("rule", ""), inventory)) for row in raw_wrong]
    events = event_records(inventory)
    changed = []
    targets = {
        WIKI / "history" / "WRONG-QUESTIONS.md": render_wrong_index(raw_wrong, inventory),
        WIKI / "history" / "CONVERSATION-EVENTS.md": render_event_index(events),
    }
    for path, content in targets.items():
        if write_if_changed(path, content):
            changed.append(path.relative_to(WIKI).as_posix())
    for stem in inventory:
        path = WIKI / "rules" / f"{stem}.md"
        if update_rule(path, backlink_block(stem, wrong, events)):
            changed.append(path.relative_to(WIKI).as_posix())
    return {
        "status": "updated" if changed else "no-op",
        "wrong_rows": len(wrong),
        "wrong_rows_linked": sum(bool(row["rules"]) for row in wrong),
        "events": len(events),
        "events_linked_to_rules": sum(bool(item["rules"]) for item in events),
        "rule_pages": len(inventory),
        "changed_pages": changed,
    }


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
