#!/usr/bin/env python3
"""Incrementally project supported learning events into the Obsidian Wiki.

The first supported profile is TQ-108.  The design is deliberately conservative:
source slices are fingerprinted, only generated projection files are changed, and
authority/learning source files are never written.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from pathlib import Path


BUILD_DATE = "2026-09-11"
ENGINE_VERSION = "1.3"
PROFILE = "TQ-108"
START = "<!-- INCREMENTAL:START -->"
END = "<!-- INCREMENTAL:END -->"
LEGACY_CONTRAST = "contrasts/Article 14与DPIA咨询期限.md"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def frontmatter(page_type: str, page_id: str, title: str, sources: list[str], aliases: list[str] | None = None, **fields: str) -> str:
    lines = [
        "---", f"type: {page_type}", f"id: {page_id}", f'title: "{title}"',
        "generated: true", f"generated_on: {BUILD_DATE}",
    ]
    lines.extend(f"{key}: {value}" for key, value in fields.items())
    lines.append("source_refs:")
    lines.extend(f'  - "{source}"' for source in sources)
    if aliases:
        lines.append("ref_aliases:")
        lines.extend(f'  - "{alias}"' for alias in aliases)
    lines.extend(["---", "", f"# {title}", ""])
    return "\n".join(lines)


def write_if_changed(path: Path, content: str, changed: list[str], wiki: Path) -> None:
    normalized = content.rstrip() + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == normalized:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized, encoding="utf-8")
    changed.append(str(path.relative_to(wiki)))


def load_event(root: Path) -> dict[str, str] | None:
    with (root / "10-逐题作答记录.csv").open(encoding="utf-8", newline="") as handle:
        rows = [
            {key: value for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
            if row["question_id"] == PROFILE
        ]
    return rows[-1] if rows else None


def load_note_slice(root: Path) -> str:
    text = (root / "08-CIPPE结构化记忆笔记.md").read_text(encoding="utf-8")
    match = re.search(
        r"^## 笔记 \d+｜Article 14 告知时钟 vs Article 36 DPIA 咨询时钟\n.*?(?=^## 笔记 |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise RuntimeError("TQ-108 note slice is missing")
    return match.group(0).rstrip()


def load_db(root: Path) -> tuple[dict, dict[str, dict]]:
    db = root / "knowledge_base" / "cippe_kb.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.row_factory = sqlite3.Row
        question_row = connection.execute(
            "SELECT q_no,pdf_page,stem,source_answer,verification_status,verified_answer,verified_on "
            "FROM questions WHERE q_no=108"
        ).fetchone()
        section_rows = connection.execute(
            "SELECT section_no,title,start_page,end_page,text FROM sections "
            "WHERE section_no IN ('8.1.3','8.1.5','11.5.1.3')"
        ).fetchall()
    if not question_row:
        raise RuntimeError("Question 108 is missing from the database")
    sections = {row["section_no"]: dict(row) for row in section_rows}
    required = {"8.1.3", "8.1.5", "11.5.1.3"}
    if set(sections) != required:
        raise RuntimeError(f"Missing textbook sections: {sorted(required - set(sections))}")
    return dict(question_row), sections


def source_fingerprints(event: dict[str, str], note: str, question: dict, sections: dict[str, dict]) -> dict[str, str]:
    return {
        "engine": sha(ENGINE_VERSION),
        "event:TQ-108": sha(json.dumps(event, ensure_ascii=False, sort_keys=True)),
        "note:article-14-36-clocks": sha(note),
        "db:question-108": sha(json.dumps(question, ensure_ascii=False, sort_keys=True)),
        **{
            f"db:section-{number}": sha(json.dumps(section, ensure_ascii=False, sort_keys=True))
            for number, section in sorted(sections.items())
        },
    }


def source_page(section: dict) -> tuple[str, str]:
    number = section["section_no"]
    title = f"教材 §{number} — {section['title']}"
    filename = title.rstrip("?") + ".md"
    text = frontmatter(
        "source", f"TEXTBOOK-{number}", title, ["knowledge_base/cippe_kb.sqlite3"],
        authority_status="original_text_not_current_law_certification",
    )
    text += (
        f"**教材页码：** {section['start_page']}–{section['end_page']}  \n"
        "**使用限制：** 本页是教材数据库正文入口，不等于现行法独立核验。\n\n"
        f"## 正文\n\n{section['text']}\n"
    )
    return filename, text


def generated_pages(event: dict[str, str], question: dict, sections: dict[str, dict]) -> dict[str, str]:
    sources = ["08-CIPPE结构化记忆笔记.md", "10-逐题作答记录.csv", "knowledge_base/cippe_kb.sqlite3"]
    pages: dict[str, str] = {}

    for section in sections.values():
        filename, text = source_page(section)
        pages[f"sources/{filename}"] = text

    title = "Article 14(3) — 间接取得数据的告知时点"
    text = frontmatter("rule", "RULE-GDPR-14-3-NOTICE-TIMING", title, sources, aliases=["GDPR14(3)"], authority_status="derived")
    text += (
        "间接取得个人数据时，应在考虑具体处理情形后的合理期间内提供信息，最迟不得超过一个月。"
        "如更早首次联系数据主体，应最迟在首次联系时提供；如更早首次向其他接收者披露，应最迟在首次披露时提供。\n\n"
        "`at the latest at the time of the first communication` 不是首次联系之后再开始计时。\n\n"
        "教材锚点：[[教材 §8.1.5 — When information should be provided to data subjects]]。\n\n"
        "关联：[[TQ 108]] · [[Controller]] · [[Article 14与DPIA咨询期限|Article 14 告知时钟与 Article 36 DPIA 咨询时钟]] · [[把 Article 36 的 six weeks 迁移到 Article 14]]。\n"
    )
    pages[f"rules/{title}.md"] = text

    title = "Article 36(2) — DPIA 事先咨询时钟"
    text = frontmatter("rule", "RULE-GDPR-36-2-PRIOR-CONSULTATION-CLOCK", title, sources, aliases=["GDPR36(2)"], authority_status="derived")
    text += (
        "当 DPIA 显示处理会造成控制者无法通过措施充分降低的高风险时，应在处理前咨询监管机关。"
        "监管机关通常应在收到咨询请求后最多八周内书面告知；考虑处理复杂性时，可延长六周。\n\n"
        "教材锚点：[[教材 §11.5.1.3 — What if the processing is still high risk]]。\n\n"
        "关联：[[Supervisory Authority]] · [[Article 14与DPIA咨询期限|Article 14 告知时钟与 Article 36 DPIA 咨询时钟]] · [[把 Article 36 的 six weeks 迁移到 Article 14]]。\n"
    )
    pages[f"rules/{title}.md"] = text

    title = "把 Article 36 的 six weeks 迁移到 Article 14"
    text = frontmatter(
        "misconception", "MC-A-CROSS-RULE-DEADLINE-14-36", title,
        ["10-逐题作答记录.csv", "08-CIPPE结构化记忆笔记.md"],
        authority_status="personal_learning_evidence", cipp_id="CIPP-023",
    )
    text += (
        "错误模型：记住了一个熟悉的期限，却没有先确认期限属于哪个主体、程序与法律房间。\n\n"
        "替代判断轴：先识别 `controller 向数据主体告知`，还是 `DPA 对 prior consultation 作出回应`。\n\n"
        "## 证据与连接\n\n- [[TQ 108]]\n- [[Article 14(3) — 间接取得数据的告知时点]]\n"
        "- [[Article 36(2) — DPIA 事先咨询时钟]]\n- [[Article 14与DPIA咨询期限|Article 14 告知时钟与 Article 36 DPIA 咨询时钟]]\n"
    )
    pages[f"misconceptions/{title}.md"] = text

    title = "Article 14 告知时钟与 Article 36 DPIA 咨询时钟"
    text = frontmatter("contrast", "CONTRAST-ARTICLE-14-36-CLOCKS", title, sources, authority_status="derived")
    text += (
        "| 触发事实 | 规则 | 时间 |\n|---|---|---|\n"
        "| 数据从本人以外来源取得 | [[Article 14(3) — 间接取得数据的告知时点]] | 合理期间内，最迟一个月 |\n"
        "| 将首次联系数据主体 | [[Article 14(3) — 间接取得数据的告知时点]] | 最迟在首次联系时 |\n"
        "| 将首次向他人披露数据 | [[Article 14(3) — 间接取得数据的告知时点]] | 最迟在首次披露时 |\n"
        "| DPIA 留有无法充分降低的高风险 | [[Article 36(2) — DPIA 事先咨询时钟]] | 通常最多 8 周；复杂时可再延长 6 周 |\n\n"
        "关联：[[TQ 108]] · [[把 Article 36 的 six weeks 迁移到 Article 14]]。\n"
    )
    pages["contrasts/Article 14与DPIA咨询期限.md"] = text

    title = "TQ 108"
    text = frontmatter(
        "question", "TQ-108", title,
        ["knowledge_base/cippe_kb.sqlite3", "knowledge_base/article_map/question_map.json"],
        teacher_only="true", source_status="exam_provenance_unverified",
        verification_status=question["verification_status"],
    )
    text += (
        "> [!warning] 教师侧导航页\n> 本页暴露题目关联和答案状态，不用于独立作答入口。\n\n"
        f"**任务：** 间接告知的最迟时间  \n**题库页码：** {question['pdf_page']}  \n"
        f"**数据库核验状态：** `{question['verification_status']}`  \n"
        f"**题库印刷答案：** `{question['source_answer']}`（题源真实性与法律核验仍分开）\n\n"
        "## 关联\n\n- [[Article 14(3) — 间接取得数据的告知时点]]\n"
        "- [[Article 36(2) — DPIA 事先咨询时钟]]\n- [[Controller]]\n"
        "- [[把 Article 36 的 six weeks 迁移到 Article 14]]\n"
    )
    pages["questions/TQ 108.md"] = text

    event_id = f"LE-{event['date'].replace('-', '')}-TQ-108"
    title = "Article 14(3)｜首次联系与一个月期限"
    text = frontmatter(
        "learning_event", event_id, title, ["10-逐题作答记录.csv"],
        immutable="true", mode=event["mode"], verification_status=event["verification_status"],
    )
    text += (
        f"**当时选择：** `{event['answer'] or '未记录'}`  \n**信心：** `{event['confidence'] or '未报告'}`  \n"
        f"**是否正确：** `{event['correct'] or '未判定'}`  \n**理由状态：** `{event['reasoning_status'] or '未记录'}`  \n"
        f"**下次回测：** `{event['next_review'] or '未安排'}`\n\n## 当时记录\n\n{event['notes']}\n\n"
        "## 关联\n\n- [[TQ 108]]\n- [[把 Article 36 的 six weeks 迁移到 Article 14]]\n"
    )
    pages[f"learning-events/{event_id}.md"] = text
    return pages


def baseline_contrast() -> str:
    """Restore the useful pre-Agent page when the TQ-108 event is removed."""
    title = "Article 14 告知时钟与 Article 36 DPIA 咨询时钟"
    text = frontmatter(
        "contrast", "CONTRAST-ARTICLE-14-36-CLOCKS", title,
        ["08-CIPPE结构化记忆笔记.md", "06-CIPPE知识库与调用协议.md", "knowledge_base/cippe_kb.sqlite3"],
        authority_status="derived",
    )
    text += (
        "这是两个不同的法律房间：\n\n"
        "| 看到的触发事实 | 规则 | 时间 |\n|---|---|---|\n"
        "| 数据从本人以外来源取得 | Article 14(3)(a) | 合理期间内，最迟一个月 |\n"
        "| 将首次联系数据主体 | Article 14(3)(b) | 最迟在首次联系时（之前或同时） |\n"
        "| 将首次向他人披露数据 | Article 14(3)(c) | 最迟在首次披露时 |\n"
        "| DPIA 显示存在无法充分降低的高风险 | Article 36(2) prior consultation | DPA 通常最多 8 周；复杂时可再加 6 周 |\n\n"
        "## 最容易错的语言\n\n"
        "`at the latest at the time of the first communication` 不等于 `after the first communication`。"
        "首次联系是最迟节点，不是允许事后补告知的起点。\n\n"
        "`six weeks` 属于 Article 36 咨询时钟的可能延长，不属于 Article 14 间接告知期限。\n\n"
        "教材定位：§8.1.5（When information should be provided to data subjects）；"
        "§11.5.1.3（What if the processing is still high risk?）。完整正文入口为 `knowledge_base/cippe_kb.sqlite3`。\n"
    )
    return text


def update_home(home: Path, active: bool, changed: list[str], wiki: Path) -> None:
    text = home.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise RuntimeError("HOME.md is missing incremental markers; run build_pilot.py once")
    replacement = f"{START}\n{END}"
    updated = re.sub(re.escape(START) + r".*?" + re.escape(END), replacement, text, flags=re.DOTALL)
    write_if_changed(home, updated, changed, wiki)


def remove_owned(wiki: Path, owned: list[str], changed: list[str]) -> None:
    for relative in owned:
        path = wiki / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "generated: true" not in text:
            raise RuntimeError(f"Refusing to remove non-generated page: {relative}")
        path.unlink()
        changed.append(relative)


def sync(root: Path, wiki: Path, state_file: Path) -> dict:
    event = load_event(root)
    previous = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    changed: list[str] = []

    if event is None:
        if previous.get("profiles", {}).get(PROFILE, {}).get("active"):
            removable = [
                page for page in previous["profiles"][PROFILE].get("owned_pages", [])
                if page != LEGACY_CONTRAST
            ]
            remove_owned(wiki, removable, changed)
            write_if_changed(wiki / LEGACY_CONTRAST, baseline_contrast(), changed, wiki)
            update_home(wiki / "HOME.md", False, changed, wiki)
        fingerprints: dict[str, str] = {}
        owned_pages: list[str] = []
        active = False
    else:
        note = load_note_slice(root)
        question, sections = load_db(root)
        fingerprints = source_fingerprints(event, note, question, sections)
        profile_before = previous.get("profiles", {}).get(PROFILE, {})
        if profile_before.get("active") and profile_before.get("fingerprints") == fingerprints:
            return {"status": "no-op", "profile": PROFILE, "changed_pages": []}
        pages = generated_pages(event, question, sections)
        stale_pages = sorted(set(profile_before.get("owned_pages", [])) - set(pages))
        remove_owned(wiki, stale_pages, changed)
        for relative, content in sorted(pages.items()):
            write_if_changed(wiki / relative, content, changed, wiki)
        update_home(wiki / "HOME.md", True, changed, wiki)
        owned_pages = sorted(pages)
        active = True

    state = {
        "schema_version": 1,
        "generated_on": BUILD_DATE,
        "profiles": {
            PROFILE: {
                "active": active,
                "fingerprints": fingerprints,
                "owned_pages": owned_pages,
            }
        },
    }
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": "updated" if changed else "state-only", "profile": PROFILE, "changed_pages": changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--wiki", type=Path)
    parser.add_argument("--state", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    wiki = (args.wiki or root / "wiki").resolve()
    state = (args.state or wiki / "_state" / "manifest.json").resolve()
    report = sync(root, wiki, state)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
