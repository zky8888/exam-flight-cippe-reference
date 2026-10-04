#!/usr/bin/env python3
"""Classify proposed Wiki actions and build the review inbox/report."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def classify(kind: str, schema: dict) -> str:
    for level, key in (
        ("auto", "auto_action_kinds"),
        ("needs_review", "review_action_kinds"),
        ("forbidden", "forbidden_action_kinds"),
    ):
        if kind in schema[key]:
            return level
    raise ValueError(f"Unknown action kind: {kind}")


def validate_casebook(casebook: dict, schema: dict) -> list[dict]:
    results = []
    seen = set()
    for case in casebook["cases"]:
        if case["case_id"] in seen:
            raise ValueError(f"Duplicate case_id: {case['case_id']}")
        seen.add(case["case_id"])
        if case["event_type"] not in schema["event_types"]:
            raise ValueError(f"Invalid event_type in {case['case_id']}")
        if case["knowledge_effect"] not in schema["knowledge_effects"]:
            raise ValueError(f"Invalid knowledge_effect in {case['case_id']}")
        if case["misconception_effect"] not in schema["misconception_effects"]:
            raise ValueError(f"Invalid misconception_effect in {case['case_id']}")
        for action in case["actions"]:
            actual = classify(action["kind"], schema)
            results.append({
                "case_id": case["case_id"],
                "event_key": case["event_key"],
                "kind": action["kind"],
                "target": action["target"],
                "expected": action["expected_level"],
                "actual": actual,
                "passed": actual == action["expected_level"],
                "evidence": case["evidence"],
            })
    return results


def render_report(results: list[dict], case_count: int) -> str:
    counts = Counter(item["actual"] for item in results)
    failures = [item for item in results if not item["passed"]]
    review = [item for item in results if item["actual"] == "needs_review"]
    blocked = [item for item in results if item["actual"] == "forbidden"]
    lines = [
        "# Wiki Agent 维护与安全报告", "",
        f"- 真实案例：{case_count}",
        f"- 动作断言：{len(results)}",
        f"- 自动处理：{counts['auto']}",
        f"- 等待评审：{counts['needs_review']}",
        f"- 已阻止：{counts['forbidden']}",
        f"- 分类失败：{len(failures)}", "",
        "## 已自动处理", "",
        "仅允许明确关系链接、索引更新和不可变学习事件投影。", "",
        "## 等待评审", "",
    ]
    lines.extend(f"- `{item['event_key']}`：`{item['kind']}` — {item['evidence']}" for item in review)
    lines.extend(["", "## 已阻止", ""])
    lines.extend(f"- `{item['event_key']}`：`{item['kind']}` → `{item['target']}`" for item in blocked)
    lines.extend([
        "", "## 无变化", "",
        "- 原始题目、答案核验、题源状态与学习状态均未写回。",
    ])
    lines.extend(["", "## 结论", ""])
    lines.append("全部回归断言通过。" if not failures else "存在分类失败，本轮不得自动写入。")
    return "\n".join(lines) + "\n"


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=root)
    args = parser.parse_args()
    root = args.root.resolve()
    wiki = root / "wiki"
    schema = load(wiki / "agent" / "CLASSIFICATION_SCHEMA.json")
    casebook = load(wiki / "agent" / "CASEBOOK.json")
    results = validate_casebook(casebook, schema)
    if any(not item["passed"] for item in results):
        raise SystemExit("Safety classification regression failed")

    review_items = [item for item in results if item["actual"] == "needs_review"]
    inbox = {
        "schema_version": 1,
        "status": "pending_user_review",
        "items": review_items,
    }
    inbox_path = wiki / "review" / "pending.json"
    report_path = wiki / "reports" / "latest.md"
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_text(json.dumps(inbox, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(results, len(casebook["cases"])), encoding="utf-8")
    print(json.dumps({
        "cases": len(casebook["cases"]),
        "assertions": len(results),
        "passed": len(results),
        "review_items": len(review_items),
        "forbidden_blocked": sum(item["actual"] == "forbidden" for item in results),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
