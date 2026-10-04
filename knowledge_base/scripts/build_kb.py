#!/usr/bin/env python3
"""Build a local, searchable CIPP/E source index from the user's two PDFs.

The database deliberately keeps the question bank's printed answer separate from
the verified answer. Printed answers are source data, not legal authority.
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pdfplumber


DEFAULT_TEXTBOOK = Path("materials/textbook.pdf")
DEFAULT_QUESTION_BANK = Path("materials/question-bank.pdf")

CHAPTER_TITLES = {
    1: "Origins and Development of European Data Protection Law",
    2: "European Union Institutions",
    3: "Legislative Framework",
    4: "Data Protection Concepts",
    5: "Territorial and Material Scope of the General Data Protection Regulation",
    6: "Data Processing Principles",
    7: "Lawful Processing Criteria",
    8: "Information Provision Obligations",
    9: "Data Subject Rights",
    10: "Security of Personal Data",
    11: "Accountability Requirements",
    12: "International Data Transfers",
    13: "Supervision and Enforcement",
    14: "Employment Relationships",
    15: "Surveillance Activities",
    16: "Direct Marketing",
    17: "Internet Technology and Communications",
    18: "Outsourcing",
}

TOPIC_RULES = {
    "european_framework": (
        "council of europe", "convention 108", "european council", "european commission",
        "european parliament", "council of the european union", "court of justice",
        "european court of human rights", "oecd guidelines",
    ),
    "personal_data": (
        "personal data", "pseudonym", "anonymous", "anonymised", "anonymized",
        "identifiable", "filing system", "special categor", "biometric", "genetic data",
    ),
    "controller_processor": (
        "controller", "processor", "joint controller", "sub-processor", "on behalf of",
        "documented instructions",
    ),
    "territorial_scope": (
        "territorial scope", "article 3", "offering goods", "offer goods", "monitoring their behaviour",
        "monitoring their behavior", "establishment in the union", "eu customers",
    ),
    "principles": (
        "purpose limitation", "data minimisation", "data minimization", "storage limitation",
        "accuracy principle", "lawfulness, fairness", "fairness and transparency",
        "integrity and confidentiality", "accountability principle",
    ),
    "lawful_basis": (
        "legal basis", "lawful basis", "legitimate interest", "consent", "performance of a contract",
        "legal obligation", "vital interests", "public task",
    ),
    "data_subject_rights": (
        "right of access", "access request", "right to erasure", "right to rectification",
        "right to restriction", "right to object", "data portability", "automated decision",
        "data subject request", "article 15", "article 17", "article 20", "article 22",
    ),
    "security_breach": (
        "personal data breach", "data breach", "72 hours", "supervisory authority",
        "security measures", "security obligations", "incident response",
    ),
    "accountability_dpia_dpo": (
        "data protection impact assessment", "dpia", "data protection officer", "dpo",
        "privacy by design", "protection by design", "records of processing",
    ),
    "international_transfers": (
        "international transfer", "international data transfer", "cross-border", "transborder",
        "third country", "adequacy decision", "standard contractual clauses", "binding corporate rules",
    ),
    "employment": (
        "employee", "employer", "workplace", "employment", "works council", "whistleblowing", "byod",
    ),
    "surveillance": (
        "surveillance", "monitoring", "cctv", "video surveillance", "facial recognition", "location data",
    ),
    "direct_marketing_eprivacy": (
        "direct marketing", "marketing email", "electronic mail", "eprivacy", "cookie", "sms", "telephone marketing",
    ),
    "technology_ai_cloud": (
        "artificial intelligence", "algorithm", "cloud", "internet of things", "social media",
        "search engine", "mobile app", "online behavioural advertising", "online behavioral advertising",
    ),
    "enforcement": (
        "fine", "penalty", "enforcement", "lead supervisory authority", "one-stop shop", "complaint",
    ),
}

SEED_CARDS = [
    {
        "card_id": "KB-001",
        "title": "Convention 108 and the EU framework",
        "domain": "European framework",
        "source_sections": "1.7; 2.2-2.7; 3.2-3.4",
        "exam_focus": "Identify which instrument or institution belongs to the Council of Europe or the EU; recognise their overlapping treatment of cross-border data flows.",
        "rule_summary": "Convention 108/108+ belongs to the Council of Europe framework, while GDPR belongs to the EU framework. Different frameworks may still regulate the same subject, including cross-border data flows.",
        "bank_questions": "2, 4, 5, 9, 10",
        "common_traps": "Treating the Council of Europe as an EU institution; confusing European Council, Council of the EU and Council of Europe; assuming different frameworks cannot overlap.",
        "verification_status": "partially_verified",
    },
    {
        "card_id": "KB-002",
        "title": "Personal, pseudonymised, anonymised and encrypted data",
        "domain": "Data protection concepts",
        "source_sections": "4.2; 4.3; 4.5; 5.3",
        "exam_focus": "Decide whether data remain personal data and whether GDPR applies.",
        "rule_summary": "Pseudonymised or encrypted data normally remain personal data when individuals can still be identified using additional information. Properly anonymised data fall outside GDPR.",
        "bank_questions": "13, 14, 158",
        "common_traps": "Equating removal of names, pseudonymisation or encryption with anonymisation.",
        "verification_status": "partially_verified",
    },
    {
        "card_id": "KB-003",
        "title": "GDPR territorial scope",
        "domain": "Scope",
        "source_sections": "5.2",
        "exam_focus": "Apply establishment, offering-goods/services and behaviour-monitoring tests; reject mere accessibility and citizenship traps.",
        "rule_summary": "For a non-EU organisation, mere website accessibility is insufficient. Article 3(2) looks for offering goods or services to people in the Union or monitoring behaviour occurring there.",
        "bank_questions": "15; 306-307 scenario group",
        "common_traps": "Using citizenship, server location or mere accessibility as the sole trigger.",
        "verification_status": "partially_verified",
    },
    {
        "card_id": "KB-004",
        "title": "Purpose limitation, minimisation and transparency",
        "domain": "Processing principles",
        "source_sections": "6.2; 6.3; 6.4; 8.1; 8.4",
        "exam_focus": "Separate why/compatible further use, what/how much is necessary, and what was communicated to the data subject.",
        "rule_summary": "Purpose limitation controls why data are processed and compatible further use. Data minimisation controls whether the data are adequate, relevant and limited to what is necessary. Transparency controls what is clearly communicated.",
        "bank_questions": "Use topic search; mapping is generated from all 307 questions.",
        "common_traps": "Treating every new use as excess collection; treating every vague purpose as only a notice problem.",
        "verification_status": "partially_verified",
    },
    {
        "card_id": "KB-005",
        "title": "Legitimate interests assessment and DPIA",
        "domain": "Lawful basis and accountability",
        "source_sections": "7.2; 11.5",
        "exam_focus": "Distinguish the LIA required to rely on legitimate interests from the high-risk threshold for a DPIA; recognise when both are needed.",
        "rule_summary": "An LIA tests purpose, necessity and balancing when legitimate interests are relied on. A DPIA is required before processing likely to result in high risk to individuals' rights and freedoms. The tests are independent and can both apply.",
        "bank_questions": "79-80; 301; 303",
        "common_traps": "Assuming sensitive data are the only DPIA trigger; treating LIA and DPIA as alternatives.",
        "verification_status": "partially_verified",
    },
    {
        "card_id": "KB-006",
        "title": "Data-subject request timing",
        "domain": "Data subject rights",
        "source_sections": "9.2-9.12",
        "exam_focus": "Separate the one-month response period and possible two-month extension from the 72-hour breach-notification rule.",
        "rule_summary": "Controllers generally act on rights requests within one month. Where necessary, the period may be extended by two further months, but the data subject must be informed within the first month with reasons.",
        "bank_questions": "3; 77; 164; 300; 302",
        "common_traps": "Applying the 72-hour breach deadline to data-subject rights requests.",
        "verification_status": "partially_verified",
    },
    {
        "card_id": "KB-007",
        "title": "Personal-data breach notification paths",
        "domain": "Security",
        "source_sections": "10.3; 10.5",
        "exam_focus": "Identify who notifies whom, the timing and the risk threshold.",
        "rule_summary": "Processor to controller: without undue delay. Controller to supervisory authority: within 72 hours unless the breach is unlikely to result in risk. Controller to affected individuals: without undue delay when high risk is likely.",
        "bank_questions": "Use topic search; mapping is generated from all 307 questions.",
        "common_traps": "Applying 72 hours to every recipient; confusing risk with high risk.",
        "verification_status": "partially_verified",
    },
    {
        "card_id": "KB-008",
        "title": "Controller, processor and assessment ownership",
        "domain": "Roles and outsourcing",
        "source_sections": "4.4; 11.2; 18.2-18.4",
        "exam_focus": "Identify who determines purposes and essential means, who acts on instructions and who owns legal-basis/DPIA decisions.",
        "rule_summary": "The controller determines purposes and essential means and owns the legal-basis and accountability decisions. A processor acts on documented instructions and provides required assistance; using data for an independent purpose can make it a controller for that processing.",
        "bank_questions": "161-163; 304",
        "common_traps": "Assuming the party physically handling or hosting data is automatically the controller; assigning the controller's assessment ownership to the processor.",
        "verification_status": "partially_verified",
    },
]


@dataclass
class PageText:
    page_no: int
    text: str


def clean_text(text: str | None, question_bank: bool = False) -> str:
    text = text or ""
    if question_bank:
        text = text.translate(str.maketrans("", "", "店铺学习小："))
        text = re.sub(r"(?<=[A-Za-z])6(?=[A-Za-z])", "", text)
        # The repeated watermark sometimes lands after a QUESTION label on the
        # same line (for example, "QUESTION 54 6 6"). Remove only that suffix.
        text = re.sub(r"(?m)^(QUESTION\s+\d{1,3})\s+(?:6\s*){2,10}$", r"\1", text)
        text = re.sub(r"(?m)^\s*(?:6\s*){1,10}$", "", text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf(path: Path, question_bank: bool = False) -> list[PageText]:
    pages: list[PageText] = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            pages.append(PageText(index, clean_text(page.extract_text(), question_bank)))
    return pages


def chapter_starts(pages: list[PageText]) -> dict[int, int]:
    starts: dict[int, int] = {}
    for page in pages:
        if page.page_no < 16:
            continue
        first_lines = page.text.splitlines()[:5]
        for line in first_lines:
            match = re.fullmatch(r"CHAPTER\s+(\d{1,2})", line, flags=re.I)
            if match:
                number = int(match.group(1))
                if number in CHAPTER_TITLES and number not in starts:
                    starts[number] = page.page_no
    return starts


def active_chapter(page_no: int, starts: dict[int, int]) -> int | None:
    candidates = [number for number, start in starts.items() if start <= page_no]
    return max(candidates) if candidates else None


def extract_sections(pages: list[PageText], starts: dict[int, int]) -> list[dict]:
    events: list[dict] = []
    section_pattern = re.compile(r"^(\d{1,2}\.\d+(?:\.\d+)*)\s+(.{2,160})$")
    flat_lines: list[tuple[int, str]] = []
    for page in pages:
        if page.page_no < min(starts.values(), default=10**9):
            continue
        flat_lines.extend((page.page_no, line) for line in page.text.splitlines())

    for index, (page_no, line) in enumerate(flat_lines):
        match = section_pattern.match(line)
        if not match:
            continue
        section_no, title = match.groups()
        chapter_no = int(section_no.split(".")[0])
        if chapter_no != active_chapter(page_no, starts):
            continue
        if len(title.split()) > 22:
            continue
        events.append({
            "section_no": section_no,
            "chapter_no": chapter_no,
            "title": title.strip(),
            "start_page": page_no,
            "line_index": index,
        })

    unique_events: list[dict] = []
    seen: set[str] = set()
    for event in events:
        if event["section_no"] in seen:
            continue
        seen.add(event["section_no"])
        unique_events.append(event)

    for i, event in enumerate(unique_events):
        end_index = unique_events[i + 1]["line_index"] if i + 1 < len(unique_events) else len(flat_lines)
        body_lines = [line for _, line in flat_lines[event["line_index"] + 1:end_index]]
        event["end_page"] = flat_lines[end_index - 1][0] if end_index > event["line_index"] else event["start_page"]
        event["text"] = "\n".join(body_lines).strip()
        event.pop("line_index", None)
    return unique_events


def locate_page(position: int, offsets: list[int], page_numbers: list[int]) -> int:
    index = bisect.bisect_right(offsets, position) - 1
    return page_numbers[max(index, 0)]


def split_options(pre_answer: str) -> tuple[str, dict[str, str]]:
    markers = list(re.finditer(r"(?m)^\s*([A-D])\.\s+", pre_answer))
    chosen: list[re.Match] | None = None
    for i in range(max(0, len(markers) - 8), len(markers) - 3):
        group = markers[i:i + 4]
        if [item.group(1) for item in group] == ["A", "B", "C", "D"]:
            chosen = group
    if not chosen:
        return pre_answer.strip(), {}
    stem = pre_answer[:chosen[0].start()].strip()
    options: dict[str, str] = {}
    for index, marker in enumerate(chosen):
        start = marker.end()
        end = chosen[index + 1].start() if index + 1 < len(chosen) else len(pre_answer)
        options[marker.group(1)] = re.sub(r"\s+", " ", pre_answer[start:end]).strip()
    return stem, options


def classify_topics(text: str) -> list[str]:
    lowered = text.lower()
    return [topic for topic, keywords in TOPIC_RULES.items() if any(keyword in lowered for keyword in keywords)]


def parse_questions(pages: list[PageText]) -> list[dict]:
    chunks: list[str] = []
    offsets: list[int] = []
    page_numbers: list[int] = []
    total = 0
    for page in pages:
        marker = f"\n<<<PDF_PAGE_{page.page_no}>>>\n"
        piece = marker + page.text + "\n"
        offsets.append(total)
        page_numbers.append(page.page_no)
        chunks.append(piece)
        total += len(piece)
    joined = "".join(chunks)
    question_matches = list(re.finditer(r"(?m)^QUESTION\s+(\d{1,3})\s*$", joined))
    questions: list[dict] = []
    for index, match in enumerate(question_matches):
        q_no = int(match.group(1))
        end = question_matches[index + 1].start() if index + 1 < len(question_matches) else len(joined)
        raw = joined[match.end():end]
        raw = re.sub(r"\n?<<<PDF_PAGE_\d+>>>\n?", "\n", raw).strip()
        answer_match = re.search(r"(?i)Correct\s+Answer\s*:\s*([A-D])", raw)
        source_answer = answer_match.group(1).upper() if answer_match else None
        pre_answer = raw[:answer_match.start()].strip() if answer_match else raw
        after_answer = raw[answer_match.end():].strip() if answer_match else ""
        stem, options = split_options(pre_answer)

        after_answer = re.sub(r"(?im)^Section\s*:\s*\(none\)\s*$", "", after_answer)
        after_answer = re.sub(r"(?im)^Explanation/Reference\s*:\s*$", "", after_answer)
        reference_match = re.search(r"(?is)\bReference\s*:\s*(.+)$", after_answer)
        source_reference = re.sub(r"\s+", " ", reference_match.group(1)).strip() if reference_match else ""
        explanation = after_answer[:reference_match.start()].strip() if reference_match else after_answer.strip()
        explanation = re.sub(r"(?im)^Explanation\s*:\s*", "", explanation).strip()

        searchable = "\n".join([stem] + [f"{key}. {value}" for key, value in options.items()])
        status = "needs_review" if q_no in {8, 11, 12} else "unverified"
        questions.append({
            "q_no": q_no,
            "pdf_page": locate_page(match.start(), offsets, page_numbers),
            "stem": stem,
            "options": options,
            "source_answer": source_answer,
            "source_explanation": explanation,
            "source_reference": source_reference,
            "verification_status": status,
            "topics": classify_topics(searchable),
            "searchable": searchable,
        })
    return questions


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        DROP TABLE IF EXISTS sources;
        DROP TABLE IF EXISTS pages;
        DROP TABLE IF EXISTS chapters;
        DROP TABLE IF EXISTS sections;
        DROP TABLE IF EXISTS questions;
        DROP TABLE IF EXISTS question_options;
        DROP TABLE IF EXISTS question_topics;
        DROP TABLE IF EXISTS knowledge_cards;
        DROP TABLE IF EXISTS variant_questions;
        DROP TABLE IF EXISTS pages_fts;
        DROP TABLE IF EXISTS sections_fts;
        DROP TABLE IF EXISTS questions_fts;

        CREATE TABLE sources (
            source_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            path TEXT NOT NULL,
            page_count INTEGER NOT NULL,
            extracted_on TEXT NOT NULL
        );
        CREATE TABLE pages (
            source_id TEXT NOT NULL,
            page_no INTEGER NOT NULL,
            text TEXT NOT NULL,
            PRIMARY KEY (source_id, page_no)
        );
        CREATE TABLE chapters (
            chapter_no INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            start_page INTEGER NOT NULL,
            end_page INTEGER NOT NULL
        );
        CREATE TABLE sections (
            section_no TEXT PRIMARY KEY,
            chapter_no INTEGER NOT NULL,
            title TEXT NOT NULL,
            start_page INTEGER NOT NULL,
            end_page INTEGER NOT NULL,
            text TEXT NOT NULL
        );
        CREATE TABLE questions (
            q_no INTEGER PRIMARY KEY,
            pdf_page INTEGER NOT NULL,
            stem TEXT NOT NULL,
            source_answer TEXT,
            source_explanation TEXT NOT NULL,
            source_reference TEXT NOT NULL,
            verification_status TEXT NOT NULL DEFAULT 'unverified',
            verified_answer TEXT,
            verified_analysis TEXT,
            verified_source TEXT,
            verified_on TEXT
        );
        CREATE TABLE question_options (
            q_no INTEGER NOT NULL,
            option_key TEXT NOT NULL,
            option_text TEXT NOT NULL,
            PRIMARY KEY (q_no, option_key)
        );
        CREATE TABLE question_topics (
            q_no INTEGER NOT NULL,
            topic TEXT NOT NULL,
            PRIMARY KEY (q_no, topic)
        );
        CREATE TABLE knowledge_cards (
            card_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            domain TEXT NOT NULL,
            source_sections TEXT NOT NULL,
            exam_focus TEXT NOT NULL,
            rule_summary TEXT NOT NULL,
            bank_questions TEXT NOT NULL,
            common_traps TEXT NOT NULL,
            verification_status TEXT NOT NULL,
            last_verified TEXT
        );
        CREATE TABLE variant_questions (
            variant_id TEXT PRIMARY KEY,
            card_id TEXT NOT NULL,
            parent_q_no INTEGER,
            target_misconception TEXT NOT NULL,
            stem TEXT NOT NULL,
            options_json TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            analysis TEXT NOT NULL,
            source_basis TEXT NOT NULL,
            created_on TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        );

        CREATE VIRTUAL TABLE pages_fts USING fts5(source_id, page_no UNINDEXED, text);
        CREATE VIRTUAL TABLE sections_fts USING fts5(section_no UNINDEXED, title, text);
        CREATE VIRTUAL TABLE questions_fts USING fts5(q_no UNINDEXED, stem, options, topics);
        """
    )


def write_database(
    output: Path,
    textbook_path: Path,
    bank_path: Path,
    textbook_pages: list[PageText],
    bank_pages: list[PageText],
    starts: dict[int, int],
    sections: list[dict],
    questions: list[dict],
) -> None:
    preserved = {"verifications": [], "cards": [], "variants": []}
    if output.exists():
        old = sqlite3.connect(output)
        table_names = {row[0] for row in old.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "questions" in table_names:
            preserved["verifications"] = old.execute(
                """SELECT q_no, verification_status, verified_answer, verified_analysis,
                verified_source, verified_on FROM questions
                WHERE verified_answer IS NOT NULL OR verified_analysis IS NOT NULL
                OR verified_source IS NOT NULL OR verification_status IN ('verified', 'outdated')"""
            ).fetchall()
        if "knowledge_cards" in table_names:
            preserved["cards"] = old.execute("SELECT * FROM knowledge_cards").fetchall()
        if "variant_questions" in table_names:
            preserved["variants"] = old.execute("SELECT * FROM variant_questions").fetchall()
        old.close()
        output.unlink()
    connection = sqlite3.connect(output)
    create_schema(connection)
    today = date.today().isoformat()
    connection.executemany(
        "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("TEXTBOOK-3E", "textbook", "European Data Protection: Law and Practice, Third Edition", str(textbook_path), len(textbook_pages), today),
            ("TQ-BANK", "question_bank", "CIPP-E题库", str(bank_path), len(bank_pages), today),
        ],
    )
    for source_id, pages in (("TEXTBOOK-3E", textbook_pages), ("TQ-BANK", bank_pages)):
        connection.executemany(
            "INSERT INTO pages VALUES (?, ?, ?)",
            [(source_id, page.page_no, page.text) for page in pages],
        )
        connection.executemany(
            "INSERT INTO pages_fts VALUES (?, ?, ?)",
            [(source_id, page.page_no, page.text) for page in pages],
        )

    ordered = sorted(starts.items())
    for index, (number, start) in enumerate(ordered):
        end = ordered[index + 1][1] - 1 if index + 1 < len(ordered) else len(textbook_pages)
        connection.execute(
            "INSERT INTO chapters VALUES (?, ?, ?, ?)",
            (number, CHAPTER_TITLES[number], start, end),
        )
    connection.executemany(
        "INSERT INTO sections VALUES (?, ?, ?, ?, ?, ?)",
        [(item["section_no"], item["chapter_no"], item["title"], item["start_page"], item["end_page"], item["text"]) for item in sections],
    )
    connection.executemany(
        "INSERT INTO sections_fts VALUES (?, ?, ?)",
        [(item["section_no"], item["title"], item["text"]) for item in sections],
    )

    for question in questions:
        connection.execute(
            "INSERT INTO questions (q_no, pdf_page, stem, source_answer, source_explanation, source_reference, verification_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                question["q_no"], question["pdf_page"], question["stem"], question["source_answer"],
                question["source_explanation"], question["source_reference"], question["verification_status"],
            ),
        )
        connection.executemany(
            "INSERT INTO question_options VALUES (?, ?, ?)",
            [(question["q_no"], key, value) for key, value in question["options"].items()],
        )
        connection.executemany(
            "INSERT INTO question_topics VALUES (?, ?)",
            [(question["q_no"], topic) for topic in question["topics"]],
        )
        connection.execute(
            "INSERT INTO questions_fts VALUES (?, ?, ?, ?)",
            (
                question["q_no"], question["stem"],
                "\n".join(f"{key}. {value}" for key, value in question["options"].items()),
                " ".join(question["topics"]),
            ),
        )

    connection.executemany(
        """INSERT INTO knowledge_cards
        (card_id, title, domain, source_sections, exam_focus, rule_summary, bank_questions, common_traps, verification_status, last_verified)
        VALUES (:card_id, :title, :domain, :source_sections, :exam_focus, :rule_summary, :bank_questions, :common_traps, :verification_status, NULL)""",
        SEED_CARDS,
    )
    if preserved["cards"]:
        connection.executemany(
            "INSERT OR REPLACE INTO knowledge_cards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            preserved["cards"],
        )
    if preserved["verifications"]:
        connection.executemany(
            """UPDATE questions SET verification_status = ?, verified_answer = ?,
            verified_analysis = ?, verified_source = ?, verified_on = ? WHERE q_no = ?""",
            [(status, answer, analysis, source, verified_on, q_no) for q_no, status, answer, analysis, source, verified_on in preserved["verifications"]],
        )
    if preserved["variants"]:
        connection.executemany(
            "INSERT OR REPLACE INTO variant_questions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            preserved["variants"],
        )
    connection.commit()
    connection.close()


def write_reports(output_dir: Path, starts: dict[int, int], sections: list[dict], questions: list[dict]) -> None:
    answer_count = sum(1 for item in questions if item["source_answer"])
    option_count = sum(1 for item in questions if len(item["options"]) == 4)
    missing_questions = sorted(set(range(1, 308)) - {item["q_no"] for item in questions})
    report = f"""# CIPP/E 知识库构建报告

- 构建日期：{date.today().isoformat()}
- 教材章节：{len(starts)} / 18
- 教材小节：{len(sections)}
- 题库题目：{len(questions)} / 307
- 已解析题库参考答案：{answer_count} / {len(questions)}
- 已完整解析四个选项：{option_count} / {len(questions)}
- 缺失题号：{', '.join(map(str, missing_questions)) if missing_questions else '无'}

注意：数据库中的 `source_answer` 只是题库印刷答案。只有写入 `verified_answer`、`verified_analysis`、`verified_source` 和 `verified_on` 后，才表示已按现行规则核验。
"""
    (output_dir / "build_report.md").write_text(report, encoding="utf-8")

    card_lines = ["# 知识卡索引", "", "这些卡片是日常学习的首批稳定入口；后续按考试大纲和错题继续扩充。", ""]
    for card in SEED_CARDS:
        card_lines.extend([
            f"## {card['card_id']} · {card['title']}", "",
            f"- 领域：{card['domain']}",
            f"- 教材定位：{card['source_sections']}",
            f"- 考点：{card['exam_focus']}",
            f"- 核心规则：{card['rule_summary']}",
            f"- 题库入口：{card['bank_questions']}",
            f"- 常见陷阱：{card['common_traps']}",
            f"- 核验状态：{card['verification_status']}", "",
        ])
    (output_dir / "cards" / "INDEX.md").write_text("\n".join(card_lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--textbook", type=Path, default=DEFAULT_TEXTBOOK)
    parser.add_argument("--question-bank", type=Path, default=DEFAULT_QUESTION_BANK)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "cards").mkdir(parents=True, exist_ok=True)
    textbook_pages = extract_pdf(args.textbook)
    bank_pages = extract_pdf(args.question_bank, question_bank=True)
    starts = chapter_starts(textbook_pages)
    sections = extract_sections(textbook_pages, starts)
    questions = parse_questions(bank_pages)
    write_database(
        args.output_dir / "cippe_kb.sqlite3",
        args.textbook,
        args.question_bank,
        textbook_pages,
        bank_pages,
        starts,
        sections,
        questions,
    )
    write_reports(args.output_dir, starts, sections, questions)
    print(json.dumps({
        "database": str(args.output_dir / "cippe_kb.sqlite3"),
        "textbook_pages": len(textbook_pages),
        "question_bank_pages": len(bank_pages),
        "chapters": len(starts),
        "sections": len(sections),
        "questions": len(questions),
        "answers": sum(1 for item in questions if item["source_answer"]),
        "four_option_questions": sum(1 for item in questions if len(item["options"]) == 4),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
