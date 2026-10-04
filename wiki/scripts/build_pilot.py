#!/usr/bin/env python3
"""Build the read-only DPO/DPA pilot projection for Obsidian."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from build_history_backlinks import build as build_history_backlinks
from build_rule_navigation import build as build_rule_navigation


ROOT = Path(__file__).resolve().parents[2]
WIKI = ROOT / "wiki"
DB = ROOT / "knowledge_base" / "cippe_kb.sqlite3"
QUESTION_MAP = ROOT / "knowledge_base" / "article_map" / "question_map.json"
ATTEMPTS = ROOT / "10-逐题作答记录.csv"
BUILD_DATE = "2026-09-11"

EVENT_TITLES = {
    "TQ-052": "DPO｜建议和监督不等于批准",
    "DPO-MAP-RECALL": "DPO｜Article 37、38、39 职能地图回收",
    "TQ-191": "Article 78(2)｜DPA 三个月未反馈后的司法救济",
    "DPA-CLOCK-RECALL": "Article 12 与 78｜Controller 一个月、DPA 三个月",
    "TQ-072": "Article 83｜罚款档位与具体裁量不能混为一谈",
}


def frontmatter(page_type: str, page_id: str, title: str, sources: list[str], **fields: str) -> str:
    lines = ["---", f"type: {page_type}", f"id: {page_id}", f'title: "{title}"', "generated: true", f"generated_on: {BUILD_DATE}"]
    for key, value in fields.items():
        lines.append(f"{key}: {value}")
    lines.append("source_refs:")
    lines.extend(f'  - "{source}"' for source in sources)
    lines.extend(["---", "", f"# {title}", ""])
    return "\n".join(lines)


def write_page(relative: str, text: str) -> None:
    path = WIKI / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = text.rstrip() + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != normalized:
        path.write_text(normalized, encoding="utf-8")


def load_questions() -> dict[int, dict]:
    wanted = {52, 72, 191}
    mapped = {item["q_no"]: item for item in json.loads(QUESTION_MAP.read_text(encoding="utf-8")) if item["q_no"] in wanted}
    with sqlite3.connect(DB) as connection:
        connection.row_factory = sqlite3.Row
        for row in connection.execute(
            "SELECT q_no,pdf_page,stem,source_answer,verification_status,verified_answer,verified_on FROM questions WHERE q_no IN (52,72,191)"
        ):
            mapped[row["q_no"]]["db"] = dict(row)
    if set(mapped) != wanted:
        raise RuntimeError(f"Missing question sources: {sorted(wanted - set(mapped))}")
    return mapped


def load_sections() -> dict[str, dict]:
    wanted = {"11.6.2", "13.2.3", "13.3.5", "13.6.1", "13.6.2"}
    with sqlite3.connect(DB) as connection:
        connection.row_factory = sqlite3.Row
        rows = {row["section_no"]: dict(row) for row in connection.execute(
            "SELECT section_no,title,start_page,end_page,text FROM sections WHERE section_no IN ('11.6.2','13.2.3','13.3.5','13.6.1','13.6.2')"
        )}
    if set(rows) != wanted:
        raise RuntimeError(f"Missing textbook sections: {sorted(wanted - set(rows))}")
    return rows


def load_events() -> list[dict[str, str]]:
    wanted = {"TQ-052", "DPO-MAP-RECALL", "TQ-191", "DPA-CLOCK-RECALL", "TQ-072"}
    with ATTEMPTS.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["question_id"] in wanted]
    found = {row["question_id"] for row in rows}
    if found != wanted:
        raise RuntimeError(f"Missing learning events: {sorted(wanted - found)}")
    return rows


def build_sources(sections: dict[str, dict]) -> None:
    for section_no, section in sections.items():
        title = f"教材 §{section_no} — {section['title']}"
        body = frontmatter(
            "source", f"TEXTBOOK-{section_no}", title,
            ["knowledge_base/cippe_kb.sqlite3"],
            authority_status="original_text_not_current_law_certification",
        )
        body += (
            f"**教材页码：** {section['start_page']}–{section['end_page']}  \n"
            "**使用限制：** 本页是教材数据库正文入口，不等于现行法独立核验。\n\n"
            "## 正文\n\n"
            f"{section['text']}\n"
        )
        # Obsidian resolves ordinary wikilinks by filename, so keep the source
        # filename identical to the human-facing page title.
        # Keep punctuation that is meaningful in the heading, but remove a
        # trailing question mark from the filename so existing concise links
        # remain stable across Obsidian and filesystem conventions.
        source_filename = title.rstrip("?")
        write_page(f"sources/{source_filename}.md", body)


def build_actors() -> None:
    pages = {
        "DPO.md": (
            "ACTOR-DPO", "DPO — 组织内部的数据保护顾问与监督者",
            "DPO 的考试主干是：[[Article 37 — DPO appointment]] → [[Article 38 — DPO position and resources]] → [[Article 39 — DPO tasks]]。\n\n"
            "DPO 可以 advise、monitor、cooperate 和 act as a contact point；这些动词不自动产生 approve 或 decide 的权力。组织仍承担合规责任。\n\n"
            "## 个人关联\n\n- [[TQ 052]]\n- [[建议监督不等于批准]]\n- [[DPO 与监管机关的权限边界]]\n"
        ),
        "Supervisory Authority.md": (
            "ACTOR-SUPERVISORY-AUTHORITY", "Supervisory Authority — 国家监管机关",
            "监管机关处理投诉、调查、采取纠正措施并可实施行政罚款；法院提供司法救济，DPO 在组织内部提供建议和监督。\n\n"
            "## 关键连接\n\n- [[Article 78(2) — DPA 三个月未告知后的司法救济]]\n- [[Article 83 — 行政罚款]]\n- [[一个月与三个月属于不同主体]]\n- [[DPO 与监管机关的权限边界]]\n"
        ),
        "Controller.md": (
            "ACTOR-CONTROLLER", "Controller — 决定目的与关键手段的责任主体",
            "本原型只保留与监管责任簇有关的连接：controller/processor 负责为 DPO 提供资源并尊重其独立性；controller 的数据主体请求时钟不得迁移为 DPA 投诉处理时钟。\n\n"
            "## 关键连接\n\n- [[Article 38 — DPO position and resources]]\n- [[一个月与三个月属于不同主体]]\n- [[DPO]]\n"
        ),
    }
    for filename, (page_id, title, content) in pages.items():
        text = frontmatter("actor", page_id, title, ["08-CIPPE结构化记忆笔记.md", "knowledge_base/cippe_kb.sqlite3"], authority_status="derived") + content
        write_page(f"actors/{filename}", text)


def build_rules() -> None:
    pages = {
        "Article 37 — DPO appointment.md": (
            "RULE-GDPR-37-DPO-APPOINTMENT", "Article 37 — DPO appointment",
            "先判断是否触发任命门：公共机关/机构；核心活动包含大规模定期和系统监控；或核心活动包含大规模处理 Article 9 或 Article 10 数据。\n\n"
            "关联：[[DPO]] · [[Article 38 — DPO position and resources]] · [[Article 39 — DPO tasks]]\n"
        ),
        "Article 38 — DPO position and resources.md": (
            "RULE-GDPR-38-DPO-POSITION", "Article 38 — DPO position and resources",
            "组织需要让 DPO 适时参与，提供完成任务和维持专业知识所需的资源与数据/处理活动接入，并保障独立性、直接向最高管理层报告以及避免利益冲突。\n\n"
            "教材锚点：[[教材 §11.6.2 — What is the role of the DPO]]。\n\n"
            "关联：[[DPO]] · [[TQ 052]] · [[建议监督不等于批准]]\n"
        ),
        "Article 39 — DPO tasks.md": (
            "RULE-GDPR-39-DPO-TASKS", "Article 39 — DPO tasks",
            "核心任务动词：inform and advise、monitor compliance、advise on and monitor DPIA、cooperate with the supervisory authority、act as its contact point。\n\n"
            "这些任务不把 DPO 变成 controller、监管机关或一般审批者。关联：[[DPO]] · [[DPO 与监管机关的权限边界]]。\n"
        ),
        "Article 78(2) — DPA 三个月未告知后的司法救济.md": (
            "RULE-GDPR-78-2-DPA-INACTIVITY", "Article 78(2) — DPA 三个月未告知后的司法救济",
            "当监管机关未处理投诉，或在三个月内没有告知投诉的进展或结果，数据主体可以针对监管机关寻求有效司法救济。\n\n"
            "教材锚点：[[教材 §13.3.5 — Regulating the regulators]]。\n\n"
            "关联：[[Supervisory Authority]] · [[TQ 191]] · [[一个月与三个月属于不同主体]]\n"
        ),
        "Article 83 — 行政罚款.md": (
            "RULE-GDPR-83-FINES", "Article 83 — 行政罚款",
            "考试先区分两个最高罚款档次：Article 83(4) 与 Article 83(5)–(6)。Article 25 属于较低档；Articles 5–7 和 Chapter III 权利属于较高档。\n\n"
            "最高档次不是自动罚款数额。是否罚以及具体金额仍须结合 Article 83(2) 个案因素，并满足有效、相称和劝阻性。\n\n"
            "教材锚点：[[教材 §13.6.1 — Factors to be considered before fines can be imposed]] · [[教材 §13.6.2 — Maximum fines for undertakings and]]。\n\n"
            "关联：[[Supervisory Authority]] · [[TQ 072]] · [[罚款上限不等于自动罚款]]\n"
        ),
    }
    for filename, (page_id, title, content) in pages.items():
        text = frontmatter("rule", page_id, title, ["08-CIPPE结构化记忆笔记.md", "knowledge_base/cippe_kb.sqlite3"], authority_status="derived") + content
        write_page(f"rules/{filename}", text)


def build_contrasts() -> None:
    pages = {
        "DPO 与监管机关的权限边界.md": (
            "CONTRAST-DPO-SA-POWERS", "DPO 与监管机关的权限边界",
            "| 主体 | 主要动词 | 不应误读为 |\n|---|---|---|\n| [[DPO]] | advise、monitor、cooperate、contact | 普遍批准权或监管执法权 |\n| [[Supervisory Authority]] | investigate、order、authorize、fine | 组织内部顾问 |\n| 法院 | judicial review、remedy、compensation | 行政监管机关 |\n"
        ),
        "一个月与三个月属于不同主体.md": (
            "CONTRAST-ARTICLE-12-78-CLOCKS", "一个月与三个月属于不同主体",
            "| 触发事实 | 主体 | 时钟 | 法律房间 |\n|---|---|---|---|\n| 数据主体向 controller 提出权利请求 | [[Controller]] | 通常一个月回应 | Article 12 |\n| 向 DPA 投诉后未获进展/结果信息 | [[Supervisory Authority]] | 三个月后司法救济 | [[Article 78(2) — DPA 三个月未告知后的司法救济]] |\n\n关联错因：[[把 Controller 的一个月迁移给 DPA]]。\n"
        ),
        "罚款上限不等于自动罚款.md": (
            "CONTRAST-FINE-TIER-DISCRETION", "罚款上限不等于自动罚款",
            "先判断违规落入 Article 83(4) 还是 83(5)–(6) 的最高档次，再看 Article 83(2) 个案因素。上限、实际是否罚款和具体金额是不同判断。\n\n关联：[[Article 83 — 行政罚款]] · [[TQ 072]] · [[把所有违规理解为同档自动罚款]]。\n"
        ),
    }
    for filename, (page_id, title, content) in pages.items():
        text = frontmatter("contrast", page_id, title, ["08-CIPPE结构化记忆笔记.md", "01-错题库.md"], authority_status="derived") + content
        write_page(f"contrasts/{filename}", text)


def build_misconceptions() -> None:
    pages = {
        "建议监督不等于批准.md": (
            "MC-A-ADVICE-IS-APPROVAL", "建议监督不等于批准", "CIPP-027", "TQ 052",
            "把 DPO 的 advisory/monitoring role 误读成批准行为准则的权力。替代判断轴：先识别 advise/monitor，还是 decide/approve。",
        ),
        "把 Controller 的一个月迁移给 DPA.md": (
            "MC-A-CLOCK-WRONG-ACTOR", "把 Controller 的一个月迁移给 DPA", "CIPP-028", "TQ 191",
            "把 Article 12 的 controller 回应时钟迁移到 Article 78(2) 的 DPA 投诉不作为。替代判断轴：看到期限先确认 actor 和程序。",
        ),
        "把所有违规理解为同档自动罚款.md": (
            "MC-K-FINE-TIERS", "把所有违规理解为同档自动罚款", "CIPP-029", "TQ 072",
            "尚未形成 Article 83 两档分类，并可能把最高上限当成实际自动罚款。替代轴：先分类档次，再进入 Article 83(2) 个案裁量。",
        ),
    }
    for filename, (page_id, title, cipp_id, question, description) in pages.items():
        text = frontmatter("misconception", page_id, title, ["01-错题库.md", "10-逐题作答记录.csv"], authority_status="personal_learning_evidence", cipp_id=cipp_id)
        text += f"{description}\n\n## 证据与连接\n\n- [[{question}]]\n"
        write_page(f"misconceptions/{filename}", text)


def build_questions(questions: dict[int, dict]) -> None:
    links = {
        52: ["Article 38 — DPO position and resources", "DPO", "建议监督不等于批准"],
        72: ["Article 83 — 行政罚款", "Supervisory Authority", "把所有违规理解为同档自动罚款"],
        191: ["Article 78(2) — DPA 三个月未告知后的司法救济", "Supervisory Authority", "把 Controller 的一个月迁移给 DPA"],
    }
    for q_no, question in questions.items():
        db = question["db"]
        title = f"TQ {q_no:03d}"
        text = frontmatter(
            "question", f"TQ-{q_no:03d}", title,
            ["knowledge_base/cippe_kb.sqlite3", "knowledge_base/article_map/question_map.json"],
            teacher_only="true", source_status="exam_provenance_unverified",
            verification_status=db["verification_status"],
        )
        text += (
            "> [!warning] 教师侧导航页\n"
            "> 本页可能暴露题目关联和印刷答案，不用于独立练习入口。\n\n"
            f"**任务：** {question['task']}  \n"
            f"**题库页码：** {db['pdf_page']}  \n"
            f"**数据库核验状态：** `{db['verification_status']}`  \n"
            f"**题库印刷答案：** `{db['source_answer'] or '未记录'}`（不等于独立核验答案）\n\n"
            "## 关联\n\n" + "\n".join(f"- [[{link}]]" for link in links[q_no]) + "\n"
        )
        write_page(f"questions/{title}.md", text)


def build_events(events: list[dict[str, str]]) -> None:
    links = {
        "TQ-052": ["TQ 052", "建议监督不等于批准"],
        "DPO-MAP-RECALL": ["DPO", "Article 37 — DPO appointment", "Article 38 — DPO position and resources", "Article 39 — DPO tasks"],
        "TQ-191": ["TQ 191", "把 Controller 的一个月迁移给 DPA"],
        "DPA-CLOCK-RECALL": ["一个月与三个月属于不同主体"],
        "TQ-072": ["TQ 072", "把所有违规理解为同档自动罚款"],
    }
    for sequence, row in enumerate(events, start=1):
        event_id = f"LE-{row['date'].replace('-', '')}-{row['question_id']}-{sequence:02d}"
        title = EVENT_TITLES.get(row["question_id"], f"{row['date']} — {row['question_id']}")
        text = frontmatter(
            "learning_event", event_id, title,
            ["10-逐题作答记录.csv"],
            immutable="true", mode=row["mode"], verification_status=row["verification_status"],
        )
        text += (
            f"**当时选择/输出：** `{row['answer'] or '未记录'}`  \n"
            f"**信心：** `{row['confidence'] or '未报告'}`  \n"
            f"**是否正确：** `{row['correct'] or '未判定'}`  \n"
            f"**理由状态：** `{row['reasoning_status'] or '未记录'}`  \n"
            f"**下次回测：** `{row['next_review'] or '未安排'}`\n\n"
            "## 当时记录\n\n"
            f"{row['notes']}\n\n"
            "## 关联\n\n" + "\n".join(f"- [[{link}]]" for link in links[row["question_id"]]) + "\n"
        )
        write_page(f"learning-events/{event_id}.md", text)


def build_home() -> None:
    text = frontmatter("index", "INDEX-CIPPE-WIKI", "CIPP/E Wiki — 监管责任簇原型", ["wiki/_meta/SCHEMA.md", "wiki/_meta/WRITEBACK_POLICY.md"], authority_status="generated_index")
    text += """> [!warning] 教师侧知识投影
> 本 Wiki 包含题目关联和个人错因，不作为作答前的独立练习入口。原始数据库和学习记录仍是真相源。

## 从主体进入

- [[DPO]]
- [[Supervisory Authority]]
- [[Controller]]

<!-- RULE-NAV:START -->
## 从规则进入

- [[Article 37 — DPO appointment]]
- [[Article 38 — DPO position and resources]]
- [[Article 39 — DPO tasks]]
- [[Article 78(2) — DPA 三个月未告知后的司法救济]]
- [[Article 83 — 行政罚款]]
<!-- RULE-NAV:END -->

## 从个人错误模型进入

- [[建议监督不等于批准]]
- [[把 Controller 的一个月迁移给 DPA]]
- [[把所有违规理解为同档自动罚款]]

## 从对比进入

- [[DPO 与监管机关的权限边界]]
- [[一个月与三个月属于不同主体]]
- [[罚款上限不等于自动罚款]]

## 原型题目

- [[TQ 052]]
- [[TQ 072]]
- [[TQ 191]]

<!-- INCREMENTAL:START -->
<!-- INCREMENTAL:END -->

## 维护规则

- [[SCHEMA]]
- [[WRITEBACK_POLICY]]
"""
    write_page("HOME.md", text)


def main() -> None:
    questions = load_questions()
    sections = load_sections()
    events = load_events()
    build_sources(sections)
    build_actors()
    build_rules()
    build_contrasts()
    build_misconceptions()
    build_questions(questions)
    build_events(events)
    build_home()
    build_history_backlinks()
    build_rule_navigation(WIKI)
    print("Built CIPP/E Obsidian pilot projection.")


if __name__ == "__main__":
    main()
