#!/usr/bin/env python3
"""Validate a conversation-derived event, apply safe projection, and queue review work."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from build_object_index import ensure_current
from safety_review import classify, load
REQUIRED = {
    "schema_version", "event_key", "event_type", "correctness", "answer_status",
    "rule_refs", "conversation_text", "evidence_quote", "analysis_summary",
    "knowledge_effect_candidate", "misconception_effect_candidate", "proposed_actions",
}

IMPACT_POLICY = {
    "new_rule": ("review_new_rule", True, "候选指向新规则；建立正式法律对象前必须审核来源和边界。"),
    "add_boundary": ("review_existing_pages", True, "候选可能扩展既有规则边界；保留旧正文并进入补充评审。"),
    "add_exception": ("review_existing_pages", True, "候选可能增加例外；不得未经审核直接改变旧规则适用范围。"),
    "strengthen_existing_rule": ("review_existing_pages", True, "候选为既有规则增加案例或解释；先进入定向补充评审。"),
    "contradict_existing_note": ("review_conflict", True, "候选与既有笔记可能冲突；必须并列保留并完成来源核验。"),
    "no_knowledge_change": ("auto_evidence_only", False, "本次只增加学习证据和链接，不修改稳定知识页。"),
    "unknown": ("review_unknown_impact", True, "现有证据不足以判断知识影响，保持待审核。"),
}

EVENT_TITLES = {
    "CLAR-20260901-ARTICLE10-TWO-ROUTES": "Article 10｜持牌机构不等于官方机关",
    "CLAR-20260904-ARTICLE22-HUMAN-INTERVENTION": "Article 22｜人工介入处在两个不同层次",
    "CLAR-20260909-ARTICLE6-SELECTION-FUNNEL": "Article 6｜目的不等于合法依据",
    "CLAR-20260911-ART14-36": "Article 14 与 36｜一个月和 six weeks 不能互换",
    "CLAR-20260912-ART83-ROPA": "RoPA 与 DPIA｜字段要求不等于证据无需保留",
    "CLAR-20260912-BCR-SA-ROLES": "BCR｜主管监管机关与 EDPB 分别做什么",
    "CLAR-20260912-COUNCILS-MNEMONIC": "欧洲机构｜三个 Council 名称怎么区分",
    "CLAR-20260913-COE-EU-COURTS": "欧洲制度｜Council of Europe、EU 与法院",
    "CLAR-20260913-FLUTTER-BCR-OPINION": "BCR｜Flutter 审批意见案例",
    "CLAR-CHATGPT-6AA63C5C-ARTICLE6-49-LAYERS": "Article 6 与 49｜处理许可和传输例外是两层",
    "CLAR-CHATGPT-6AA6B7B4-ARTICLE42-CERTIFICATION-TEETH": "Article 42/46｜Certification 为什么需要法律约束力",
    "CLAR-CHATGPT-6AA7FC05-ARTICLE49-DEROGATIONS": "Article 49｜Derogations 为什么只是特殊例外出口",
    "CORR-20260913-ADEQUACY-VALIDITY-PATH": "Article 45｜Commission 调整决定，CJEU 判断效力",
    "RETEST-20260913-TRANSFERS-INTEGRATED": "国际传输｜Adequacy、SCC 与 BCR 综合回测",
    "TQ-065-20260912": "SCC｜签了合同仍要评估第三国法律",
    "TQ-125-REPAIR1-20260913": "Article 42/46｜认证机制必须配合可执行承诺",
    "TQ-127-20260913": "Article 46 与 49｜工具和特殊情形不能混用",
    "TQ-219-REPAIR3-20260913": "Chapter V｜人在境外不等于发生国际传输",
    "TQ-256-20260913": "TIA｜补充措施必须在现实中有效",
    "TQ-288-REPAIR1-20260913": "DPF｜核对组织是否在名单及认证范围内",
    "VAR-SCHREMS-DPF-INTEGRATION-20260913-01-REPAIR2": "DPF｜Article 45 路径与 Article 46 工具分开",
    "VAR-TIA-MEASURES-PACKAGE-20260913-01": "TIA｜密钥留在 EEA 的有效加密模型",
    "VAR-TIA-NO-EFFECTIVE-MEASURE-20260913-01": "TIA｜没有有效措施时必须暂停传输",
}


def validate(candidate: dict, schema: dict) -> list[str]:
    errors = []
    missing = sorted(REQUIRED - candidate.keys())
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
    if errors:
        return errors
    if candidate["schema_version"] != 1:
        errors.append("unsupported schema_version")
    if not re.fullmatch(r"[A-Z0-9-]+", candidate["event_key"]):
        errors.append("invalid event_key")
    if candidate["event_type"] not in schema["event_types"]:
        errors.append("invalid event_type")
    if candidate["knowledge_effect_candidate"] not in {*schema["knowledge_effects"], "unknown"}:
        errors.append("invalid knowledge_effect_candidate")
    if candidate["misconception_effect_candidate"] not in {*schema["misconception_effects"], "unknown"}:
        errors.append("invalid misconception_effect_candidate")
    if not candidate["evidence_quote"] or candidate["evidence_quote"] not in candidate["conversation_text"]:
        errors.append("evidence_quote is not present in conversation_text")
    if not candidate["rule_refs"]:
        errors.append("rule_refs must not be empty")
    if not candidate.get("display_title") and candidate["event_key"] not in EVENT_TITLES:
        errors.append("display_title is required for new learning events")
    kinds = [action.get("kind") for action in candidate["proposed_actions"]]
    if "project_learning_event" not in kinds:
        errors.append("project_learning_event action is required")
    for kind in kinds:
        try:
            classify(kind, schema)
        except ValueError as exc:
            errors.append(str(exc))
    return errors


def resolve_links(candidate: dict, index: dict) -> tuple[list[str], list[str]]:
    objects = index["objects"]
    links = []
    unknown_refs = []
    for ref in candidate["rule_refs"]:
        position = index["by_ref"].get(ref)
        if position is None:
            unknown_refs.append(ref)
        else:
            links.append(objects[position]["wikilink"])
    for action in candidate["proposed_actions"]:
        if action.get("kind") != "add_explicit_link":
            continue
        target = str(action.get("target", ""))
        if target.startswith("wiki/"):
            target = target[5:]
        position = index["by_path"].get(target)
        if position is not None:
            links.append(objects[position]["wikilink"])
    return list(dict.fromkeys(links)), unknown_refs


def assess_semantic_impact(candidate: dict, links: list[str], unknown_refs: list[str]) -> dict:
    effect = candidate["knowledge_effect_candidate"]
    disposition, review_required, rationale = IMPACT_POLICY[effect]
    if effect != "new_rule" and not links and unknown_refs:
        disposition = "review_new_rule"
        review_required = True
        rationale = "候选未解析到现有对象；需先判断是新规则、别名还是错误引用。"
    return {
        "knowledge_effect": effect,
        "disposition": disposition,
        "review_required": review_required,
        "existing_targets": links,
        "unresolved_refs": unknown_refs,
        "rationale": rationale,
    }


def render_page(candidate: dict, candidate_path: Path, links: list[str], impact: dict) -> str:
    wikilinks = [f"[[{link}]]" for link in links]
    display_title = candidate.get("display_title") or EVENT_TITLES.get(candidate["event_key"]) or candidate["event_key"]
    return "\n".join([
        "---",
        "type: learning-event",
        f"id: LE-{candidate['event_key']}",
        f'title: "{display_title}"',
        "generated: true",
        "source_refs:",
        f'  - "{candidate_path.as_posix()}"',
        "---", "",
        f"# {display_title}", "",
        f"- 事件类型：`{candidate['event_type']}`",
        f"- 知识影响候选：`{candidate['knowledge_effect_candidate']}`",
        f"- 错因影响候选：`{candidate['misconception_effect_candidate']}`",
        f"- 关联对象：{'、'.join(wikilinks) if wikilinks else '待审核'}", "",
        "## 对话证据", "",
        f"> {candidate['evidence_quote']}", "",
        "## 结构化摘要", "",
        candidate["analysis_summary"], "",
        "## 对既有页面的影响", "",
        f"- 处置：`{impact['disposition']}`",
        f"- 是否需要审核：`{'yes' if impact['review_required'] else 'no'}`",
        f"- 既有目标：{'、'.join(wikilinks) if wikilinks else '未解析到既有页面'}",
        f"- 未解析引用：{', '.join(impact['unresolved_refs']) if impact['unresolved_refs'] else '无'}",
        f"- 原因：{impact['rationale']}", "",
        "> 本页是对话事件的只读投影；不代表答案核验或掌握状态发生变化。", "",
    ])


def update_impact_ledger(wiki: Path, candidate: dict, impact: dict, projection: str) -> None:
    path = wiki / "review" / "semantic-impact.json"
    existing = load(path) if path.exists() else {"schema_version": 1, "items": []}
    item = {"event_key": candidate["event_key"], "projection": projection, **impact}
    items = [old for old in existing.get("items", []) if old.get("event_key") != candidate["event_key"]]
    items.append(item)
    items.sort(key=lambda value: value["event_key"])
    payload = {"schema_version": 1, "status": "pending_user_review" if any(x["review_required"] for x in items) else "current", "items": items}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = wiki / "reports" / "semantic-impact.md"
    lines = [
        "# Wiki 语义影响报告", "",
        "> 本报告只记录候选对稳定页面的潜在影响；需要审核的项目尚未改写正式规则正文。", "",
    ]
    for entry in items:
        targets = "、".join(f"[[{target}]]" for target in entry["existing_targets"]) or "未解析到既有页面"
        lines.extend([
            f"## {entry['event_key']}", "",
            f"- 知识影响：`{entry['knowledge_effect']}`",
            f"- 处置：`{entry['disposition']}`",
            f"- 既有目标：{targets}",
            f"- 未解析引用：{', '.join(entry['unresolved_refs']) if entry['unresolved_refs'] else '无'}",
            f"- 审核：`{'需要' if entry['review_required'] else '不需要'}`", "",
        ])
    report.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def process(candidate_path: Path, root: Path) -> dict:
    wiki = root / "wiki"
    schema = load(wiki / "agent" / "CLASSIFICATION_SCHEMA.json")
    index, index_status, index_changes = ensure_current(wiki)
    candidate = load(candidate_path)
    errors = validate(candidate, schema)
    if errors:
        raise ValueError("; ".join(errors))
    actions = [
        {**action, "level": classify(action["kind"], schema)}
        for action in candidate["proposed_actions"]
    ]
    links, unknown_refs = resolve_links(candidate, index)
    impact = assess_semantic_impact(candidate, links, unknown_refs)
    if unknown_refs:
        actions.append({"kind": "create_rule_object", "target": "wiki/review", "level": "needs_review", "refs": unknown_refs})

    page = wiki / "learning-events" / f"LE-{candidate['event_key']}.md"
    already_processed = page.exists()
    rendered = render_page(candidate, candidate_path.relative_to(root), links, impact)
    old_content = page.read_text(encoding="utf-8") if already_processed else None
    page_changed = old_content != rendered
    if page_changed:
        page.write_text(rendered, encoding="utf-8")

    review = [action for action in actions if action["level"] == "needs_review"]
    blocked = [action for action in actions if action["level"] == "forbidden"]
    output = {
        "event_key": candidate["event_key"],
        "status": "updated" if already_processed and page_changed else ("already_processed" if already_processed else "processed"),
        "projection": str(page.relative_to(root)),
        "resolved_links": links,
        "semantic_impact": impact,
        "auto": [action for action in actions if action["level"] == "auto"],
        "needs_review": review,
        "blocked": blocked,
        "source_files_changed": False,
        "object_index": {
            "status": index_status,
            "changed_paths": index_changes,
        },
    }
    review_path = wiki / "review" / "conversation-pending.json"
    existing_items = []
    if review_path.exists():
        existing = load(review_path)
        existing_items = existing.get("items", [existing] if "event_key" in existing else [])
    items = [item for item in existing_items if item.get("event_key") != output["event_key"]]
    items.append(output)
    inbox = {"schema_version": 1, "status": "pending_user_review", "items": items}
    review_path.write_text(json.dumps(inbox, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_impact_ledger(wiki, candidate, impact, str(page.relative_to(root)))
    return output


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    result = process(args.candidate.resolve(), root)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
