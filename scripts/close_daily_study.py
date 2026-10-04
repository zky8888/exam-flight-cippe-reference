#!/usr/bin/env python3
"""Run the mandatory end-of-day CIPP/E closeout gate.

This command rebuilds generated learner-facing artifacts and then verifies that
their embedded data and modification times match the current source records.
It exits non-zero on any omission, so a failed run cannot be reported as a
completed daily closeout.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DAILY_PATH = ROOT / "03-每日学习记录.md"
MAP_PATH = ROOT / "08-CIPPE备考全景地图.html"
CONTEXT_PATH = ROOT / "CURRENT-CONTEXT.md"

MAP_INPUTS = [
    DAILY_PATH,
    ROOT / "07-IAPP-BOK覆盖矩阵.md",
    ROOT / "dashboard" / "article-map.json",
    ROOT / "dashboard" / "progress-state.json",
    ROOT / "dashboard" / "cippe-dashboard.template.html",
    ROOT / "scripts" / "refresh_progress_dashboard.py",
]

CONTEXT_INPUTS = [
    ROOT / "00-CIPPE总控台.md",
    ROOT / "01-错题库.md",
    ROOT / "02-间隔复习队列.md",
    DAILY_PATH,
    ROOT / "07-IAPP-BOK覆盖矩阵.md",
    ROOT / "10-逐题作答记录.csv",
    ROOT / "wiki" / "scripts" / "build_current_context.py",
    ROOT / "scripts" / "original_question_coverage.py",
]

COVERAGE_OUTPUTS = [
    ROOT / "knowledge_base" / "original_question_coverage.json",
    ROOT / "knowledge_base" / "original_question_coverage.md",
    ROOT / "knowledge_base" / "article_map" / "待审核题按规则分组.md",
]

COVERAGE_INPUTS = [
    ROOT / "knowledge_base" / "article_map" / "question_map.json",
    ROOT / "knowledge_base" / "article_map" / "concepts.json",
    ROOT / "knowledge_base" / "cippe_kb.sqlite3",
    ROOT / "10-逐题作答记录.csv",
    ROOT / "scripts" / "original_question_coverage.py",
]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_step(label: str, *command: str) -> None:
    print(f"[closeout] {label}")
    subprocess.run(command, cwd=ROOT, check=True)


def extract_dashboard_payload(text: str) -> dict[str, object]:
    match = re.search(r"const DATA = (\{.*?\});\n", text, re.DOTALL)
    if not match:
        raise ValueError("Generated map does not contain an embedded DATA payload")
    return json.loads(match.group(1))


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def assert_fresh(output: Path, inputs: list[Path]) -> None:
    if not output.exists():
        raise ValueError(f"Missing generated artifact: {display_path(output)}")
    missing = [path for path in inputs if not path.exists()]
    if missing:
        names = ", ".join(display_path(path) for path in missing)
        raise ValueError(f"Missing source files: {names}")
    newest_input = max(path.stat().st_mtime_ns for path in inputs)
    if output.stat().st_mtime_ns < newest_input:
        raise ValueError(f"Stale generated artifact: {display_path(output)}")


def unprojected_inbox_candidates(root: Path = ROOT) -> list[str]:
    projected_sources: set[str] = set()
    for event_path in (root / "wiki" / "learning-events").glob("*.md"):
        text = event_path.read_text(encoding="utf-8")
        projected_sources.update(re.findall(r'"(wiki/inbox/[^"\n]+\.json)"', text))
    missing: list[str] = []
    for candidate in (root / "wiki" / "inbox").glob("*.json"):
        relative = candidate.relative_to(root).as_posix()
        if relative not in projected_sources:
            missing.append(relative)
    return sorted(missing)


def comparable_payload(payload: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in payload.items() if key != "built_at"}


def validate_day_overviews(closeout_date: str, daily_text: str) -> None:
    # Historical records predate this learner-facing requirement.
    if closeout_date < "2026-09-20":
        return
    sections = {
        "开课总括": ("今日内容", "完成目标"),
        "收课总括": ("实际完成", "未完成及结转", "明日内容"),
    }
    for title, fields in sections.items():
        heading = re.compile(
            rf"^### {re.escape(closeout_date)} {title}\s*$", re.MULTILINE
        )
        match = heading.search(daily_text)
        if not match:
            raise ValueError(f"Missing {closeout_date} {title} in daily study record")
        next_heading = re.search(r"^#{1,3} ", daily_text[match.end():], re.MULTILINE)
        end = match.end() + next_heading.start() if next_heading else len(daily_text)
        body = daily_text[match.end():end]
        for field in fields:
            value = re.search(rf"^- {field}：(.+)$", body, re.MULTILINE)
            if not value or value.group(1).strip() in {"", "待填", "待定", "TODO", "..."}:
                raise ValueError(f"Missing {field} in {closeout_date} {title}")


def preflight(closeout_date: str) -> object:
    validate_day_overviews(closeout_date, DAILY_PATH.read_text(encoding="utf-8"))
    refresh = load_module(
        "refresh_progress_dashboard",
        ROOT / "scripts" / "refresh_progress_dashboard.py",
    )
    payload = refresh.build_payload()
    actual_date = str(payload["as_of"])[:10]
    if actual_date != closeout_date:
        raise ValueError(
            f"Latest structured daily row is {actual_date}, expected {closeout_date}. "
            "Write the dated table row before closing the day."
        )
    return refresh


def validate_final_state(closeout_date: str, refresh: object) -> dict[str, object]:
    assert_fresh(MAP_PATH, MAP_INPUTS)
    assert_fresh(CONTEXT_PATH, CONTEXT_INPUTS)
    for output in COVERAGE_OUTPUTS:
        assert_fresh(output, COVERAGE_INPUTS)

    expected = refresh.build_payload()
    actual = extract_dashboard_payload(MAP_PATH.read_text(encoding="utf-8"))
    if str(actual.get("as_of", ""))[:10] != closeout_date:
        raise ValueError("Map date does not match the requested closeout date")
    if comparable_payload(actual) != comparable_payload(expected):
        raise ValueError("Map payload does not match the current learning sources")

    missing = unprojected_inbox_candidates()
    if missing:
        raise ValueError("Unprojected Wiki inbox candidates: " + ", ".join(missing))
    return actual


def main() -> None:
    parser = argparse.ArgumentParser(description="Mandatory CIPP/E daily closeout gate")
    parser.add_argument(
        "--date",
        required=True,
        help="Learning date being closed, in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--wiki-status",
        required=True,
        choices=("synced", "no-new-learning"),
        help="Explicit result of the conversation-to-Wiki audit",
    )
    args = parser.parse_args()
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", args.date):
        raise SystemExit("--date must use YYYY-MM-DD")

    try:
        refresh = preflight(args.date)
        missing = unprojected_inbox_candidates()
        if missing:
            raise ValueError("Unprojected Wiki inbox candidates: " + ", ".join(missing))

        run_step(
            "project approved structured notes",
            sys.executable,
            "wiki/scripts/project_structured_notes.py",
        )
        run_step(
            "refresh Wiki history links",
            sys.executable,
            "wiki/scripts/build_history_backlinks.py",
        )
        run_step(
            "refresh Wiki rule navigation",
            sys.executable,
            "wiki/scripts/build_rule_navigation.py",
        )
        run_step(
            "refresh Wiki object index",
            sys.executable,
            "wiki/scripts/build_object_index.py",
        )
        run_step(
            "rebuild exact original-question coverage",
            sys.executable,
            "scripts/original_question_coverage.py",
        )
        run_step(
            "rebuild progress map",
            sys.executable,
            "scripts/refresh_progress_dashboard.py",
        )
        run_step(
            "rebuild current context",
            sys.executable,
            "wiki/scripts/build_current_context.py",
        )
        run_step(
            "validate Wiki projection",
            sys.executable,
            "wiki/scripts/validate_projection.py",
        )
        run_step(
            "run closeout regression tests",
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "wiki/tests",
            "-p",
            "test_*.py",
        )
        run_step(
            "run original-question coverage tests",
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
        )
        payload = validate_final_state(args.date, refresh)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"DAILY CLOSEOUT: FAIL — {error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(
        "DAILY CLOSEOUT: PASS — "
        f"date={args.date}; wiki={args.wiki_status}; "
        f"BoK={payload['bok']['touched']}/18 touched; "
        f"map={MAP_PATH.name}; context={CONTEXT_PATH.name}"
    )


if __name__ == "__main__":
    main()
