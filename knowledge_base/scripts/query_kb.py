#!/usr/bin/env python3
"""Fast local lookup for the CIPP/E SQLite knowledge base."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path


DEFAULT_DB = Path(__file__).resolve().parents[1] / "cippe_kb.sqlite3"


def fts_query(text: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
    return " OR ".join(f'"{token}"' for token in tokens)


def question_payload(connection: sqlite3.Connection, q_no: int, hide_answer: bool) -> dict | None:
    row = connection.execute(
        "SELECT q_no, pdf_page, stem, source_answer, source_explanation, source_reference, verification_status, verified_answer, verified_analysis, verified_source, verified_on FROM questions WHERE q_no = ?",
        (q_no,),
    ).fetchone()
    if not row:
        return None
    keys = ["q_no", "pdf_page", "stem", "source_answer", "source_explanation", "source_reference", "verification_status", "verified_answer", "verified_analysis", "verified_source", "verified_on"]
    payload = dict(zip(keys, row))
    payload["options"] = dict(connection.execute(
        "SELECT option_key, option_text FROM question_options WHERE q_no = ? ORDER BY option_key", (q_no,)
    ).fetchall())
    payload["topics"] = [item[0] for item in connection.execute(
        "SELECT topic FROM question_topics WHERE q_no = ? ORDER BY topic", (q_no,)
    ).fetchall()]
    audit_table = connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'question_audits'").fetchone()
    if audit_table:
        audit_row = connection.execute("SELECT audit_json FROM question_audits WHERE q_no = ?", (q_no,)).fetchone()
        if audit_row:
            audit = json.loads(audit_row[0])
            payload.update(audit["display"])
            payload["source_pages"] = audit["pages"]
            payload["source_label"] = audit["provenance"]
            payload["transcription_note"] = audit["cleaning"]
            if not hide_answer:
                payload["audit"] = audit
    if hide_answer:
        for key in ("source_answer", "source_explanation", "source_reference", "verified_answer", "verified_analysis", "verified_source", "topics"):
            payload.pop(key, None)
    return payload


def variant_payload(row: sqlite3.Row, show_answer: bool) -> dict:
    data = dict(row)
    if show_answer:
        return data
    return {
        "variant_id": data["variant_id"],
        "source_label": (f"题库改编 · 母题 #{data['parent_q_no']}" if data["parent_q_no"] is not None else "AI 独立情境题"),
        "stem": data["stem"],
        "options": json.loads(data["options_json"]),
        "status": data["status"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--question", type=int)
    parser.add_argument("--topic")
    parser.add_argument("--card")
    parser.add_argument("--variants-for-card")
    parser.add_argument("--variant")
    parser.add_argument("--package", help="Teacher course manifest; do not paste whole manifest into a quiz")
    parser.add_argument("--inventory", action="store_true", help="Preparation counters, not mastery")
    parser.add_argument("--indicator", help="Teacher lookup: official indicator and reviewed question links")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--show-answer", action="store_true")
    args = parser.parse_args()

    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    output: dict = {}

    if args.inventory:
        output['inventory'] = {
            'questions': connection.execute('SELECT count(*) FROM questions').fetchone()[0],
            'answer_status': dict(connection.execute('SELECT verification_status,count(*) FROM questions GROUP BY 1')),
            'full_question_audits': connection.execute('SELECT count(*) FROM question_audits').fetchone()[0],
            'source_text': dict(connection.execute('SELECT text_check_status,count(*) FROM source_checks GROUP BY 1')),
            'source_visual': dict(connection.execute('SELECT visual_status,count(*) FROM source_checks GROUP BY 1')),
            'official_indicator_rows': connection.execute('SELECT count(*) FROM bok_indicators').fetchone()[0],
            'candidate_routes': connection.execute('SELECT count(*) FROM indicator_routes').fetchone()[0],
            'registered_sections': connection.execute('SELECT count(*) FROM section_inventory').fetchone()[0],
            'section_review': dict(connection.execute('SELECT content_review_status,count(*) FROM section_inventory GROUP BY 1')),
            'note': '登记、候选映射、视觉核对、答案核验、完整拆解、学习证据是独立状态。',
        }
    if args.indicator:
        row = connection.execute('SELECT * FROM bok_indicators WHERE indicator_id=?',(args.indicator,)).fetchone()
        output['indicator'] = dict(row) if row else None
        route = connection.execute('SELECT * FROM indicator_routes WHERE indicator_id=?',(args.indicator,)).fetchone()
        output['candidate_route'] = dict(route) if route else None
        output['reviewed_question_links'] = [dict(r) for r in connection.execute(
            '''SELECT l.q_no,l.role,l.evidence,q.verification_status
               FROM question_indicator_links l JOIN questions q ON q.q_no=l.q_no
               WHERE l.indicator_id=? ORDER BY l.role,l.q_no''',(args.indicator,))]
        output['warning'] = '教师备课入口，含考点提示，不应在独立测试题前展示。无题号表示待映射，不等于无原题。'

    if args.question is not None:
        output["question"] = question_payload(connection, args.question, not args.show_answer)
    if args.topic:
        numbers = [row[0] for row in connection.execute(
            "SELECT q_no FROM question_topics WHERE topic = ? ORDER BY q_no LIMIT ?", (args.topic, args.limit)
        ).fetchall()]
        output["topic_questions"] = [question_payload(connection, number, not args.show_answer) for number in numbers]
    if args.card:
        row = connection.execute("SELECT * FROM knowledge_cards WHERE card_id = ?", (args.card,)).fetchone()
        output["card"] = dict(row) if row else None
    if args.variant:
        row = connection.execute("SELECT * FROM variant_questions WHERE variant_id = ?", (args.variant,)).fetchone()
        output["variant"] = variant_payload(row, args.show_answer) if row else None
    if args.package:
        table = connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'course_packages'").fetchone()
        row = connection.execute("SELECT package_json FROM course_packages WHERE package_id = ?", (args.package,)).fetchone() if table else None
        output["package"] = json.loads(row[0]) if row else None
    if args.variants_for_card:
        rows = connection.execute(
            "SELECT * FROM variant_questions WHERE card_id = ? AND status = 'active' ORDER BY created_on, variant_id LIMIT ?",
            (args.variants_for_card, args.limit),
        ).fetchall()
        output["variants"] = [variant_payload(row, args.show_answer) for row in rows]
    if args.query:
        match = fts_query(args.query)
        if match:
            output["sections"] = [dict(row) for row in connection.execute(
                "SELECT s.section_no, s.title, s.start_page, s.end_page, snippet(sections_fts, 2, '[', ']', ' … ', 24) AS excerpt FROM sections_fts JOIN sections s ON s.section_no = sections_fts.section_no WHERE sections_fts MATCH ? LIMIT ?",
                (match, args.limit),
            ).fetchall()]
            q_rows = connection.execute(
                "SELECT q.q_no, q.pdf_page, snippet(questions_fts, 1, '[', ']', ' … ', 30) AS excerpt, q.verification_status FROM questions_fts JOIN questions q ON q.q_no = questions_fts.q_no WHERE questions_fts MATCH ? LIMIT ?",
                (match, args.limit),
            ).fetchall()
            output["questions"] = [dict(row) for row in q_rows]
    print(json.dumps(output, ensure_ascii=False, indent=2))
    connection.close()


if __name__ == "__main__":
    main()
