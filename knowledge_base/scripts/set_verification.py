#!/usr/bin/env python3
"""Write an independently verified answer back to the local question index."""

from __future__ import annotations

import argparse
import sqlite3
from datetime import date
from pathlib import Path


DEFAULT_DB = Path(__file__).resolve().parents[1] / "cippe_kb.sqlite3"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", type=int, required=True)
    parser.add_argument("--answer", choices=["A", "B", "C", "D"], required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--status", choices=["verified", "needs_review", "outdated"], default="verified")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    connection = sqlite3.connect(args.db)
    exists = connection.execute("SELECT 1 FROM questions WHERE q_no = ?", (args.question,)).fetchone()
    if not exists:
        raise SystemExit(f"Question {args.question} is not in the database")
    connection.execute(
        """UPDATE questions
        SET verification_status = ?, verified_answer = ?, verified_analysis = ?,
            verified_source = ?, verified_on = ?
        WHERE q_no = ?""",
        (args.status, args.answer, args.analysis, "\n".join(args.source), date.today().isoformat(), args.question),
    )
    connection.commit()
    connection.close()
    print(f"Q{args.question}: {args.status}, verified answer {args.answer}")


if __name__ == "__main__":
    main()
