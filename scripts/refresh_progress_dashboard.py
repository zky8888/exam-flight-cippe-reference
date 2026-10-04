#!/usr/bin/env python3
"""Rebuild the local CIPP/E dashboard from the study records.

The Markdown files remain the source of truth.  The small JSON state file only
stores Article-level display states that cannot be inferred safely from a BoK
cluster score.
"""

from __future__ import annotations

import json
import importlib.util
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DAILY_PATH = ROOT / "03-每日学习记录.md"
BOK_PATH = ROOT / "07-IAPP-BOK覆盖矩阵.md"
ARTICLE_MAP_PATH = ROOT / "dashboard" / "article-map.json"
STATE_PATH = ROOT / "dashboard" / "progress-state.json"
TEMPLATE_PATH = ROOT / "dashboard" / "cippe-dashboard.template.html"
OUTPUT_PATH = ROOT / "08-CIPPE备考全景地图.html"


def markdown_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def latest_daily_record(text: str) -> dict[str, str]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        if re.match(r"^\|\s*20\d{2}-\d{2}-\d{2}(?:（[^）]*）)?\s*\|", line):
            cells = markdown_cells(line)
            if len(cells) >= 9:
                rows.append(cells[:9])
    if not rows:
        raise ValueError(f"No daily record rows found in {DAILY_PATH.name}")
    # Later rows on the same calendar day are later sessions.
    _, cells = max(enumerate(rows), key=lambda item: (item[1][0][:10], item[0]))
    keys = [
        "date",
        "energy",
        "minutes",
        "theme",
        "questions",
        "reviews",
        "high_confidence_errors",
        "retained",
        "tomorrow_first_step",
    ]
    return dict(zip(keys, cells))


def bok_clusters(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    pattern = re.compile(r"^\|\s*(I|II|III|IV|V)\.[A-D]\s*\|")
    for line in text.splitlines():
        if not pattern.match(line):
            continue
        cells = markdown_cells(line)
        if len(cells) < 5 or not re.fullmatch(r"S[0-4]", cells[2]):
            continue
        rows.append(
            {
                "id": cells[0],
                "name": cells[1],
                "status": cells[2],
                "evidence": cells[3],
                "next": cells[4],
            }
        )
    if len(rows) != 18:
        raise ValueError(f"Expected 18 BoK clusters, found {len(rows)} in {BOK_PATH.name}")
    return rows


def response_count(text: str) -> int | None:
    matches = re.findall(r"有效作答(?:或判断证据)?约\s*(\d+)\s*次", text)
    return int(matches[-1]) if matches else None


def build_payload() -> dict[str, object]:
    daily_text = DAILY_PATH.read_text(encoding="utf-8")
    bok_text = BOK_PATH.read_text(encoding="utf-8")
    daily = latest_daily_record(daily_text)
    clusters = bok_clusters(bok_text)
    article_map = json.loads(ARTICLE_MAP_PATH.read_text(encoding="utf-8"))
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    coverage_path = ROOT / "scripts" / "original_question_coverage.py"
    spec = importlib.util.spec_from_file_location("original_question_coverage", coverage_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {coverage_path}")
    coverage_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(coverage_module)
    original_coverage = coverage_module.build_inventory(ROOT)
    coverage_module.write_outputs(original_coverage, ROOT)

    counts = {f"S{i}": 0 for i in range(5)}
    for cluster in clusters:
        counts[cluster["status"]] += 1

    articles: list[dict[str, str]] = []
    article_counts = {"lit": 0, "active": 0, "next": 0, "pending": 0}
    known_ids: set[str] = set()
    for group in article_map["clusters"]:
        group_articles: list[dict[str, str]] = []
        for article in group["articles"]:
            article_id = article["id"]
            known_ids.add(article_id)
            status = state["article_status"].get(article_id, "pending")
            if status not in article_counts:
                raise ValueError(f"Unknown Article status {status!r} for {article_id}")
            article_counts[status] += 1
            item = {
                **article,
                "status": status,
                "next": state.get("article_next", {}).get(article_id, "按冲刺日历推进。"),
                "cluster": group["name"],
            }
            articles.append(item)
            group_articles.append(item)
        group["articles"] = group_articles

    unknown_ids = set(state["article_status"]) - known_ids
    if unknown_ids:
        raise ValueError(f"Article state contains unknown ids: {sorted(unknown_ids)}")

    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    return {
        "as_of": daily["date"],
        "built_at": now.strftime("%Y-%m-%d %H:%M"),
        "exam_date": state["exam_date"],
        "current_bok_id": state["current_bok_id"],
        "current_route": state["current_route"],
        "daily": daily,
        "bok": {
            "clusters": clusters,
            "counts": counts,
            "touched": 18 - counts["S0"],
            "stable": counts["S3"] + counts["S4"],
            "exam_ready": counts["S4"],
        },
        "responses": response_count(bok_text),
        "original_questions": original_coverage["summary"],
        "article_groups": article_map["clusters"],
        "article_counts": article_counts,
        "article_total": len(articles),
    }


def main() -> None:
    payload = build_payload()
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    marker = "/*__CIPPE_PROGRESS_DATA__*/ null"
    if marker not in template:
        raise ValueError(f"Data marker not found in {TEMPLATE_PATH.name}")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    output = template.replace(marker, data, 1)
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(
        f"Updated {OUTPUT_PATH.name}: "
        f"BoK {payload['bok']['touched']}/18 touched, "
        f"latest closeout {payload['as_of']}."
    )


if __name__ == "__main__":
    main()
