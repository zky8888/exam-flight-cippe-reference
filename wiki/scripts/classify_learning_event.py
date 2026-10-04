#!/usr/bin/env python3
"""Convert structured, previously unseen learning events into safe Wiki proposals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from safety_review import classify, load


def infer_event(event: dict, schema: dict) -> dict:
    event_type = "retest" if event["attempt_kind"] == "retest" else "new_question"

    if not event["correct"] and event["repair_status"] == "concept_confusion":
        knowledge_effect = "add_boundary"
        misconception_effect = "new_misconception"
        semantic_actions = ["name_misconception", "supplement_rule"]
        rationale = "错误来自一个具体规则边界，需记录新错因并建议补充规则，但不能直接改稳定知识。"
    elif event["correct"] and event["repair_status"] == "rule_not_articulated":
        knowledge_effect = "strengthen_existing_rule"
        misconception_effect = "additional_evidence"
        semantic_actions = ["supplement_rule"]
        rationale = "答案正确但理由链仍缺规则字段，只能视为旧模型的后续证据，不能据此升级掌握度。"
    else:
        knowledge_effect = "no_knowledge_change"
        misconception_effect = "no_misconception"
        semantic_actions = []
        rationale = "结构化字段不足以支持语义更新，保持不变。"

    action_kinds = ["project_learning_event", *semantic_actions, "promote_mastery"]
    actions = [
        {"kind": kind, "level": classify(kind, schema)}
        for kind in action_kinds
    ]
    return {
        "event_key": event["event_key"],
        "event_type": event_type,
        "knowledge_effect": knowledge_effect,
        "misconception_effect": misconception_effect,
        "evidence": event["evidence"],
        "rationale": rationale,
        "actions": actions,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=root)
    args = parser.parse_args()
    wiki = args.root.resolve() / "wiki"
    schema = load(wiki / "agent" / "CLASSIFICATION_SCHEMA.json")
    inputs = load(wiki / "agent" / "HOLDOUT_INPUTS.json")
    results = [infer_event(event, schema) for event in inputs["cases"]]
    output = {"schema_version": 1, "mode": "holdout_inference", "results": results}
    path = wiki / "review" / "holdout-results.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"classified": len(results), "output": str(path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
