#!/usr/bin/env python3
"""Build the rule-first Wiki hub and its compact HOME entry."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from build_object_index import frontmatter, scalar


WIKI = Path(__file__).resolve().parents[1]
START = "<!-- RULE-NAV:START -->"
END = "<!-- RULE-NAV:END -->"

CATEGORIES = [
    ("基本原则与合法性", range(1, 12)),
    ("透明度与数据主体权利", range(12, 24)),
    ("治理、角色与问责", range(24, 44)),
    ("国际传输", range(44, 51)),
    ("监管、救济与责任", range(51, 100)),
]

SUMMARIES = {
    "RULE-SA-INTERACTION-MAP": "先认主体和触发条件，再区分通知、咨询、批准、投诉和配合调查；联系 SA 不等于统一适用72小时。",
    'RULE-EPRIVACY-MAP': '先拆分动作、主体和渠道，确认特别规则的适用范围；再判断 GDPR 对剩余个人数据处理的要求，并检查 Article 95 是否排除同目标的重复义务。',
    'RULE-EPRIVACY-5-3': '实际向终端存储信息或访问已存信息，先检查 ePrivacy 5(3)；GDPR legitimate interests 不能替代此处要求的同意。',
    'RULE-EPRIVACY-9': '定位数据先区分是否用于通信传输或计费；在 ePrivacy 9 范围内的 non-traffic location data，走匿名化或同意路径，不能以 legitimate interests 替换其特别门槛。',
    'RULE-EPRIVACY-5-1-6': '公开电子通信中的通信保密与 traffic data 有特别规则：不能仅凭 GDPR Article 6 基础跳过 ePrivacy 5(1) 或 6。',
    'RULE-EPRIVACY-13': 'Direct marketing 先看渠道和收件人；电子邮件/SMS、无人干预自动呼叫与传真原则上事先同意，真人电话按成员国 opt-in／opt-out 实施规则分流。',
    'RULE-GDPR-95': 'Article 95 防止对已有 ePrivacy 同目标特别义务的事项重复加上 GDPR 义务；它不是全面豁免 GDPR，也不是允许忽略 ePrivacy。',
    'RULE-BEHAVIORAL-TARGETING': 'Behavioral targeting 按动作拆解：设备存取、个人数据画像、角色分配、重大自动化决定和营销发送分别判断。',
    "RULE-AIACT-5-ANNEX-III-RISK-ROOMS": "Article 5 先筛禁止实践；未被禁止时再按 Article 6(2) 与 Annex III 判断具体高风险用途，数据法另过一门。",
    "RULE-GDPR-6-LAWFUL-BASIS-SELECTION": "先把处理目的与法律依据分开；再按事实检验专门基础，依赖 legitimate interests 时完整运行 LIA。",
    "RULE-GDPR-10-CRIMINAL-DATA": "犯罪数据先要 Article 6 基础；随后须处于官方机关控制下，或获得法律授权并配有适当保障。",
    "RULE-GDPR-14-3-NOTICE-TIMING": "间接取得数据后，应在合理期间内且最迟一个月告知；首次联系或披露更早发生时，以更早节点为准。",
    "RULE-GDPR-22-AUTOMATED-DECISIONS": "先检查纯自动化与重大影响两道门，再检查三条例外和相应保障；人工介入可能处在两个不同层次。",
    "RULE-GDPR-36-2-PRIOR-CONSULTATION-CLOCK": "DPIA 留有无法充分降低的高风险时，处理前咨询监管机关；通常 8 周，复杂时可延长 6 周。",
    "RULE-GDPR-37-DPO-APPOINTMENT": "先判断公共机关、核心活动大规模系统监控或大规模 Article 9/10 处理三类任命门槛。",
    "RULE-GDPR-38-DPO-POSITION": "DPO 必须及时参与、获得资源并保持独立，不能因履职受指示或处罚。",
    "RULE-GDPR-39-DPO-TASKS": "DPO 的核心动作是告知建议、监督、DPIA 咨询和与监管机关合作，不是替组织审批。",
    "RULE-GDPR-45-ADEQUACY": "Commission 评价目的地制度是否提供实质等同保护；覆盖范围内传输无需另找 Chapter V 保障。",
    "RULE-CHAPTER-V-TRANSFER-ACTOR-CRITERION": "地理跨境本身不足；先判断数据是否由 exporter 提供给第三国中的另一个 controller 或 processor。",
    "RULE-GDPR-47-BCR": "跨国集团为覆盖的内部传输建立统一且有约束力的规则，经主管监管机关与一致性机制批准。",
    "RULE-GDPR-49-DEROGATIONS": "仅在 adequacy 与适当保障路径不可用的具体情形下，从严检查 Article 49 的狭窄例外。",
    "RULE-GDPR-78-2-DPA-INACTIVITY": "监管机关三个月未告知投诉进展或结果时，数据主体可对监管机关寻求司法救济。",
    "RULE-GDPR-83-FINES": "先区分违规所属罚款档，再结合 Article 83(2) 因素裁量；上限不是自动罚款额。",
    "RULE-SCC-LOCAL-LAW-COMPLIANCE": "SCC 不能改变第三国法律；必须评估条款能否实际履行，并在必要时采取补充措施。",
}


def article_number(meta: str) -> int | None:
    aliases = re.findall(r'^\s+-\s+"?GDPR(\d+)', meta, re.MULTILINE)
    if aliases:
        return int(aliases[0])
    object_id = scalar(meta, "id") or ""
    match = re.search(r"RULE-GDPR-(\d+)", object_id)
    return int(match.group(1)) if match else None


def category(meta: str) -> str:
    explicit = scalar(meta, "rule_room")
    if explicit:
        return explicit
    number = article_number(meta)
    if number is not None:
        for name, numbers in CATEGORIES:
            if number in numbers:
                return name
    return "待归类规则"


def discover(wiki: Path = WIKI) -> dict[str, list[dict]]:
    impact_counts = defaultdict(int)
    impact_path = wiki / "review" / "semantic-impact.json"
    if impact_path.exists():
        for impact in json.loads(impact_path.read_text(encoding="utf-8")).get("items", []):
            if impact.get("review_required"):
                for target in impact.get("existing_targets", []):
                    impact_counts[target] += 1
    groups: dict[str, list[dict]] = defaultdict(list)
    for path in sorted((wiki / "rules").glob("*.md")):
        meta = frontmatter(path)
        if meta is None or scalar(meta, "type") != "rule":
            continue
        title = scalar(meta, "title") or path.stem
        text = path.read_text(encoding="utf-8")
        history = re.search(r"<!-- HISTORY-BACKLINKS:START -->(.*?)<!-- HISTORY-BACKLINKS:END -->", text, re.DOTALL)
        history_text = history.group(1) if history else ""
        groups[category(meta)].append({
            "title": title,
            "wikilink": path.stem,
            "id": scalar(meta, "id"),
            "article": article_number(meta),
            "summary": SUMMARIES.get(scalar(meta, "id") or "", "打开规则页查看核心判断和来源。"),
            "wrong_count": len(re.findall(r"^(?:> )?- \[\[WRONG-QUESTIONS#", history_text, re.MULTILINE)),
            "event_count": len(re.findall(r"^(?:> )?- \[\[LE-", history_text, re.MULTILINE)),
            "review_count": impact_counts[path.stem],
        })
    for items in groups.values():
        items.sort(key=lambda item: (item["article"] is None, item["article"] or 999, item["title"]))
    return dict(groups)


def ordered_groups(groups: dict[str, list[dict]]) -> list[tuple[str, list[dict]]]:
    order = [name for name, _ in CATEGORIES] + ["待归类规则"]
    known = [(name, groups[name]) for name in order if groups.get(name)]
    extras = [(name, groups[name]) for name in sorted(set(groups) - set(order))]
    return known + extras


def render_rules(groups: dict[str, list[dict]]) -> str:
    count = sum(len(items) for items in groups.values())
    sections = []
    for name, items in ordered_groups(groups):
        links = "\n\n".join(
            f"### [[{item['wikilink']}|{item['title']}]]\n\n"
            f"{item['summary']}\n\n"
            f"`错题 {item['wrong_count']} · 学习事件 {item['event_count']} · 待审核更新 {item['review_count']}`"
            for item in items
        )
        sections.append(f"## {name}（{len(items)}）\n\n{links}")
    return (
        "---\n"
        "type: index\n"
        "id: INDEX-CIPPE-RULES\n"
        'title: "CIPP/E 规则总目录"\n'
        "generated: true\n"
        "generated_on: 2026-09-13\n"
        "authority_status: generated_index\n"
        "source_refs:\n"
        '  - "wiki/rules/"\n'
        "---\n\n"
        "# CIPP/E 规则总目录\n\n"
        f"> 当前收录 **{count}** 条规则。先读一句摘要；需要时再进入规则页查看完整解释和个人学习证据。\n\n"
        + "\n\n".join(sections)
        + "\n"
    )


def render_home(groups: dict[str, list[dict]]) -> str:
    count = sum(len(items) for items in groups.values())
    return (
        "---\n"
        "type: index\n"
        "id: INDEX-CIPPE-WIKI\n"
        'title: "CIPP/E 学习 Wiki"\n'
        "generated: true\n"
        "generated_on: 2026-09-14\n"
        "authority_status: generated_index\n"
        "source_refs:\n"
        '  - "wiki/rules/"\n'
        "---\n\n"
        "# CIPP/E 学习 Wiki\n\n"
        "## 开始学习\n\n"
        f"### [[RULES|按规则复习（{count} 条）]]\n\n"
        "每条规则先显示一句核心判断，再显示与你有关的错题、对话事件和待更新数量。\n\n"
        "### [[WRONG-QUESTIONS|只看我答错过的题]]\n\n"
        "按时间查看明确答错记录；点击其中的规则返回知识主线。\n\n"
        "## 怎么看\n\n"
        "1. 平时从规则目录进入，不从文件夹逐页浏览。\n"
        "2. 先读规则的一句话摘要；只有需要复习时才展开完整笔记。\n"
        "3. 规则页底部的个人学习证据默认折叠，需要追溯时再打开。\n\n"
        "> 对话事件、来源页、审核报告和技术文件仍会自动维护，但不再放在日常首页。\n\n"
        f"{START}\n{END}\n\n"
        "<!-- INCREMENTAL:START -->\n<!-- INCREMENTAL:END -->\n\n"
        "<!-- STRUCTURED-NOTES:START -->\n<!-- STRUCTURED-NOTES:END -->\n"
    )


def write_if_changed(path: Path, content: str) -> bool:
    normalized = content.rstrip() + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == normalized:
        return False
    path.write_text(normalized, encoding="utf-8")
    return True


def build(wiki: Path = WIKI) -> dict:
    groups = discover(wiki)
    changed = []
    if write_if_changed(wiki / "RULES.md", render_rules(groups)):
        changed.append("RULES.md")
    if write_if_changed(wiki / "HOME.md", render_home(groups)):
        changed.append("HOME.md")
    return {
        "status": "updated" if changed else "no-op",
        "rule_count": sum(len(items) for items in groups.values()),
        "groups": {name: len(items) for name, items in ordered_groups(groups)},
        "changed_pages": changed,
    }


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
