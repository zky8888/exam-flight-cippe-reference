#!/usr/bin/env python3
"""Persist a useful AI variant after its legal basis and answer are checked."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date
from pathlib import Path


DEFAULT_DB = Path(__file__).resolve().parents[1] / "cippe_kb.sqlite3"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--card", required=True)
    parser.add_argument("--parent-question", type=int)
    parser.add_argument("--misconception", required=True)
    parser.add_argument("--stem", required=True)
    parser.add_argument("--options-json", required=True)
    parser.add_argument("--answer", choices=["A", "B", "C", "D"], required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--source-basis", required=True)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    options = json.loads(args.options_json)
    if sorted(options) != ["A", "B", "C", "D"]:
        raise SystemExit("options-json must contain A, B, C and D")
    connection = sqlite3.connect(args.db)
    connection.execute(
        """INSERT OR REPLACE INTO variant_questions
        (variant_id, card_id, parent_q_no, target_misconception, stem, options_json,
         correct_answer, analysis, source_basis, created_on, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
        (
            args.id, args.card, args.parent_question, args.misconception, args.stem,
            json.dumps(options, ensure_ascii=False), args.answer, args.analysis,
            args.source_basis, date.today().isoformat(),
        ),
    )
    connection.commit()
    connection.close()
    print(f"Stored variant {args.id} for {args.card}")


if __name__ == "__main__":
    main()
