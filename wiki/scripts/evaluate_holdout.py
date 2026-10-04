#!/usr/bin/env python3
"""Compare frozen holdout expectations with Agent output after inference."""

from __future__ import annotations

import json
from pathlib import Path


WIKI = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    gold = {item["event_key"]: item for item in load(WIKI / "agent" / "HOLDOUT_GOLD.json")["cases"]}
    results = load(WIKI / "review" / "holdout-results.json")["results"]
    assertions = []
    for result in results:
        expected = gold[result["event_key"]]
        for field in ("event_type", "knowledge_effect", "misconception_effect"):
            assertions.append((result["event_key"], field, result[field], expected[field]))
        levels = {item["kind"]: item["level"] for item in result["actions"]}
        for kind, level in expected["action_levels"].items():
            assertions.append((result["event_key"], kind, levels.get(kind), level))
    failures = [item for item in assertions if item[2] != item[3]]
    lines = [
        "# Wiki Agent 陌生案例留出测试", "",
        f"- 留出案例：{len(results)}",
        f"- 分类断言：{len(assertions)}",
        f"- 通过：{len(assertions) - len(failures)}",
        f"- 失败：{len(failures)}", "",
    ]
    for result in results:
        lines.extend([
            f"## {result['event_key']}", "",
            f"- 事件：`{result['event_type']}`",
            f"- 知识影响：`{result['knowledge_effect']}`",
            f"- 错因影响：`{result['misconception_effect']}`",
            f"- 判断理由：{result['rationale']}",
            "- 动作：" + "；".join(f"`{a['kind']}` → `{a['level']}`" for a in result["actions"]), "",
        ])
    lines.extend(["## 结论", ""])
    lines.append("两个陌生案例全部符合冻结预期。" if not failures else "存在偏差，暂不升级自动化。")
    (WIKI / "reports" / "holdout-evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(results), "assertions": len(assertions), "failures": len(failures)}, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
