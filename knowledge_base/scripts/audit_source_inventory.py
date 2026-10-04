#!/usr/bin/env python3
"""Reproducible source checks, not legal verification or claims of full reading.

Preserves the original extraction and all question verdicts. Removes only the
identified red watermark glyphs at PDF extraction, never arbitrary digit 6s.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("builder", Path(__file__).with_name("build_kb.py"))
builder = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)

BOK_PAGE_GROUPS = {
    4: [("I.A", 3), ("I.B", 1), ("I.C", 2)],
    5: [("II.A", 5), ("II.B", 4)], 6: [("II.C", 8)],
    7: [("III.A", 1), ("III.B", 2), ("III.C", 3)],
    8: [("III.D", 7)], 9: [("IV.A", 2), ("IV.B", 5), ("IV.C", 3)],
    10: [("IV.D", 3)], 11: [("V.A", 4), ("V.B", 3), ("V.C", 2)],
    12: [("V.D", 5)],
}
BOK_URL = "https://assets.contentstack.io/v3/assets/bltd4dd5b2d705252bc/blte39ae9567661b3d2/IAPP_Training-CIPPE_BOK.pdf"
CHAPTER_ROUTES = {
    1: ["I.A", "I.C"], 2: ["I.B"], 3: ["I.C"], 4: ["II.A"],
    5: ["IV.A"], 6: ["III.A"], 7: ["III.B", "II.C"],
    8: ["III.C"], 9: ["II.C"], 10: ["II.B", "I.C"],
    11: ["IV.B"], 12: ["III.D"], 13: ["IV.C", "IV.D"],
    14: ["V.A"], 15: ["V.B"], 16: ["V.C"],
    17: ["V.D", "V.C"], 18: ["II.B", "IV.B", "V.D"],
}


def norm(value):
    return re.sub(r"\s+", " ", value).strip()


def key(value):
    return re.sub(r"[^a-z0-9]+", " ", norm(value).lower()).strip()


def keep_glyph(obj):
    c = obj.get("non_stroking_color")
    return not (obj.get("object_type") == "char" and isinstance(c, (list, tuple))
                and len(c) == 3 and c[0] > .8 and c[1] < .2 and c[2] < .2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bank", type=Path, default=builder.DEFAULT_QUESTION_BANK)
    parser.add_argument("--bok", type=Path, required=True)
    parser.add_argument("--db", type=Path, default=ROOT / "cippe_kb.sqlite3")
    args = parser.parse_args()
    stamp = date.today().isoformat()
    bank_hash = hashlib.sha256(args.bank.read_bytes()).hexdigest()
    bank_pages = []
    with pdfplumber.open(args.bank) as pdf:
        for n, page in enumerate(pdf.pages, 1):
            text = builder.clean_text(page.filter(keep_glyph).extract_text(), question_bank=False)
            bank_pages.append(builder.PageText(n, text))
            if n % 30 == 0:
                print(f"Extracted {n}/{len(pdf.pages)} bank pages", flush=True)
    questions = builder.parse_questions(bank_pages)
    assert len(questions) == 307 and sorted(q["q_no"] for q in questions) == list(range(1, 308))
    assert all(sorted(q["options"]) == list("ABCD") and q["source_answer"] in "ABCD" for q in questions)

    indicators = []
    official_pages = []
    with pdfplumber.open(args.bok) as pdf:
        for n, page in enumerate(pdf.pages, 1):
            official_pages.append((n, page.extract_text() or ""))
            if n not in BOK_PAGE_GROUPS:
                continue
            column = page.crop((322, 0, 600, 716)).extract_text() or ""
            starts = list(re.finditer(r"(?m)^(?:Know|Understand)\b", column))
            chunks = [norm(column[m.start():starts[i+1].start() if i+1 < len(starts) else len(column)])
                      for i, m in enumerate(starts)]
            expected = sum(count for _, count in BOK_PAGE_GROUPS[n])
            assert len(chunks) == expected, (n, expected, chunks)
            cursor = 0
            for cluster, count in BOK_PAGE_GROUPS[n]:
                for i in range(count):
                    indicators.append((f"{cluster}.{i+1:02}", cluster, n, chunks[cursor]))
                    cursor += 1
    assert len(indicators) == 63

    c = sqlite3.connect(args.db)
    c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS source_checks (
      q_no INTEGER PRIMARY KEY REFERENCES questions(q_no), source_sha256 TEXT NOT NULL,
      pdf_pages TEXT NOT NULL, clean_stem TEXT NOT NULL, clean_options_json TEXT NOT NULL,
      printed_answer TEXT NOT NULL, comparison_json TEXT NOT NULL,
      text_check_status TEXT NOT NULL, visual_status TEXT NOT NULL, checked_on TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS question_families (
      family_id TEXT NOT NULL, q_no INTEGER NOT NULL, relation TEXT NOT NULL,
      review_status TEXT NOT NULL, PRIMARY KEY(family_id,q_no,relation));
    CREATE TABLE IF NOT EXISTS bok_indicators (
      indicator_id TEXT PRIMARY KEY, cluster TEXT NOT NULL, source_version TEXT NOT NULL,
      source_url TEXT NOT NULL, pdf_page INTEGER NOT NULL, official_text TEXT NOT NULL,
      registration_status TEXT NOT NULL, mapping_status TEXT NOT NULL DEFAULT 'pending',
      teaching_status TEXT NOT NULL DEFAULT 'not_assessed');
    CREATE TABLE IF NOT EXISTS section_inventory (
      section_no TEXT PRIMARY KEY REFERENCES sections(section_no), chapter_no INTEGER NOT NULL,
      start_page INTEGER NOT NULL, end_page INTEGER NOT NULL, candidate_clusters TEXT NOT NULL,
      routing_basis TEXT NOT NULL, content_review_status TEXT NOT NULL DEFAULT 'not_reviewed');
    """)
    changes = []
    exact, same_options = defaultdict(list), defaultdict(list)
    with c:
        for idx, q in enumerate(questions):
            num = q["q_no"]
            old = c.execute("SELECT * FROM questions WHERE q_no=?", (num,)).fetchone()
            old_opts = dict(c.execute("SELECT option_key,option_text FROM question_options WHERE q_no=?", (num,)))
            # Reconstruct page range up to the next QUESTION marker. References
            # can spill over as well; retain full range for later visual checking.
            start = q["pdf_page"]
            stop = questions[idx+1]["pdf_page"] if idx+1 < len(questions) else len(bank_pages)
            last = stop
            if idx+1 < len(questions):
                next_marker = f"QUESTION {questions[idx+1]['q_no']}"
                before = bank_pages[stop-1].text.split(next_marker, 1)[0].strip()
                if not before and stop > start:
                    last -= 1
            pages = list(range(start, last+1))
            comparison = {"stem_changed": norm(old["stem"]) != norm(q["stem"]),
                          "options_changed": [k for k in "ABCD" if norm(old_opts[k]) != norm(q["options"][k])],
                          "printed_answer_changed": old["source_answer"] != q["source_answer"],
                          "page_changed": old["pdf_page"] != start}
            if any(comparison.values()):
                changes.append(num)
            audit = c.execute("SELECT audit_json FROM question_audits WHERE q_no=?", (num,)).fetchone()
            visual = "previously_visually_checked" if audit else "pending"
            c.execute("""INSERT INTO source_checks VALUES(?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(q_no) DO UPDATE SET source_sha256=excluded.source_sha256,
              pdf_pages=excluded.pdf_pages,clean_stem=excluded.clean_stem,
              clean_options_json=excluded.clean_options_json,printed_answer=excluded.printed_answer,
              comparison_json=excluded.comparison_json,text_check_status=excluded.text_check_status,
              visual_status=CASE WHEN source_checks.visual_status='checked' THEN 'checked' ELSE excluded.visual_status END,
              checked_on=excluded.checked_on""",
              (num,bank_hash,json.dumps(pages),q["stem"],json.dumps(q["options"],ensure_ascii=False),
               q["source_answer"],json.dumps(comparison),"reextracted_complete",visual,stamp))
            canonical_options = sorted(key(t) for t in q["options"].values())
            exact[key(q["stem"])+"|"+"|".join(canonical_options)].append(num)
            same_options["|".join(canonical_options)].append(num)
        for kind, groups in [("same_stem_and_option_texts",exact),("same_option_texts",same_options)]:
            for text, members in groups.items():
                if len(members) < 2:
                    continue
                fid = "F-"+hashlib.sha256((kind+text).encode()).hexdigest()[:12]
                for num in members:
                    c.execute("INSERT OR IGNORE INTO question_families VALUES(?,?,?,?)",(fid,num,kind,"candidate_not_semantically_confirmed"))
        for ident, cluster, page, text in indicators:
            c.execute("""INSERT INTO bok_indicators
              (indicator_id,cluster,source_version,source_url,pdf_page,official_text,registration_status)
              VALUES(?,?,?,?,?,?,?) ON CONFLICT(indicator_id) DO UPDATE SET
              source_version=excluded.source_version,source_url=excluded.source_url,
              pdf_page=excluded.pdf_page,official_text=excluded.official_text""",
              (ident,cluster,"1.3.3",BOK_URL,page,text,"registered_from_official_pdf"))
        c.execute("""INSERT INTO sources VALUES(?,?,?,?,?,?) ON CONFLICT(source_id) DO NOTHING""",
                  ("BOK-1.3.3","exam_blueprint","IAPP CIPP/E BoK v1.3.3",BOK_URL,12,stamp))
        for n,text in official_pages:
            c.execute("INSERT OR IGNORE INTO pages VALUES(?,?,?)",("BOK-1.3.3",n,text))
        for s in c.execute("SELECT * FROM sections").fetchall():
            c.execute("""INSERT OR IGNORE INTO section_inventory
               (section_no,chapter_no,start_page,end_page,candidate_clusters,routing_basis)
               VALUES(?,?,?,?,?,?)""",(s["section_no"],s["chapter_no"],s["start_page"],s["end_page"],
                json.dumps(CHAPTER_ROUTES[s["chapter_no"]]),"chapter routing only, not a semantic content review"))
    print(json.dumps({"questions_reextracted":307,"changed_transcriptions":len(changes),"changed_q_ids":changes,
      "bok_indicators_registered":len(indicators),"sections_registered":c.execute('SELECT count(*) FROM section_inventory').fetchone()[0],
      "duplicate_candidate_groups":c.execute('SELECT count(DISTINCT family_id) FROM question_families').fetchone()[0]},ensure_ascii=False))
    c.close()


if __name__ == "__main__":
    main()
