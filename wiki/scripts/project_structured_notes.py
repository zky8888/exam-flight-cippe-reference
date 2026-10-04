#!/usr/bin/env python3
"""Project approved structured-memory sections into substantive Wiki pages."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from build_history_backlinks import build as build_history_backlinks
from build_rule_navigation import build as build_rule_navigation


ROOT = Path(__file__).resolve().parents[2]
WIKI = ROOT / "wiki"
SOURCE = ROOT / "08-CIPPE结构化记忆笔记.md"
STATE = WIKI / "_state" / "structured-notes.json"
HOME_START = "<!-- STRUCTURED-NOTES:START -->"
HOME_END = "<!-- STRUCTURED-NOTES:END -->"
HISTORY_START = "<!-- HISTORY-BACKLINKS:START -->"
HISTORY_END = "<!-- HISTORY-BACKLINKS:END -->"

SPECS = [
    {
        "heading": "原则、合法依据、权利与文件责任边界",
        "path": "contrasts/原则、合法依据、权利与文件责任边界.md",
        "type": "contrast",
        "id": "CONTRAST-PRINCIPLE-BASIS-RIGHT-RECORD",
        "aliases": ["GDPR5(1)(d)", "GDPR6", "GDPR16", "GDPR28(3)(f)", "GDPR30(2)", "GDPR35(1)"],
        "links": ["Controller", "Article 83 — 行政罚款"],
    },
    {
        "heading": "欧洲数据保护的两个房间与机构动作",
        "path": "contrasts/欧洲数据保护机构与动作地图.md",
        "type": "contrast",
        "id": "CONTRAST-EUROPE-DATA-PROTECTION-INSTITUTIONS",
        "aliases": ["TEU14", "TEU15", "TEU16", "TEU19", "ECHR", "ECTHR", "CJEU", "CONVENTION108", "CONVENTION108+"],
        "links": ["Supervisory Authority", "EDPB", "Article 45 — Adequacy decision"],
    },
    {
        "heading": "Adequacy：给“目的地制度”开的跨境通行证",
        "path": "rules/Article 45 — Adequacy decision.md",
        "type": "rule",
        "id": "RULE-GDPR-45-ADEQUACY",
        "aliases": ["GDPR45", "GDPR45(1)", "GDPR45(3)", "GDPR45(4)", "GDPR45(5)", "TFEU267", "C-362/14", "C-311/18", "C-314/85"],
        "links": ["欧洲数据保护机构与动作地图", "EDPB", "SCC — 第三国法律与履约评估", "Article 47 — Binding Corporate Rules", "Article 46 工具为什么有法律牙齿"],
        "summary": "Commission 评价目的地制度是否提供实质等同保护；覆盖范围内的传输无需另找 Article 46 工具。",
    },
    {
        "heading": "SCC 不是魔法合同：当地法律必须允许履约",
        "path": "rules/SCC — 第三国法律与履约评估.md",
        "type": "rule",
        "id": "RULE-SCC-LOCAL-LAW-COMPLIANCE",
        "aliases": ["GDPR46(2)(c)", "Decision2021/914-Clause14"],
        "links": ["Article 45 — Adequacy decision", "Article 47 — Binding Corporate Rules", "Article 46 工具为什么有法律牙齿"],
        "summary": "SCC 不能改变第三国法律；必须判断条款能否实际履行，并在必要时采取有效的补充措施。",
    },
    {
        "heading": "BCR：跨国集团内部的一本统一规则书",
        "path": "rules/Article 47 — Binding Corporate Rules.md",
        "type": "rule",
        "id": "RULE-GDPR-47-BCR",
        "aliases": ["GDPR47", "GDPR47(1)", "GDPR47(1)(b)", "GDPR47(2)(e)", "GDPR47(2)(k)", "GDPR64(1)(f)"],
        "links": ["Supervisory Authority", "EDPB", "Article 45 — Adequacy decision", "SCC — 第三国法律与履约评估", "Article 46 工具为什么有法律牙齿"],
        "summary": "跨国集团为覆盖的内部传输建立统一且有约束力的规则；主管监管机关作最终批准，EDPB 提供一致性意见。",
    },
    {
        "heading": "国际传输三道门与 Article 6 双许可证",
        "path": "contrasts/国际传输三道门与 Article 6 双许可证.md",
        "type": "contrast",
        "id": "CONTRAST-TRANSFER-LAYERS-ARTICLE6-49",
        "aliases": ["GDPR44", "GDPR49", "GDPR6-vs-GDPR49", "GDPR44-49-layering"],
        "links": ["原则、合法依据、权利与文件责任边界", "Article 45 — Adequacy decision", "SCC — 第三国法律与履约评估", "Article 47 — Binding Corporate Rules", "Article 46 工具为什么有法律牙齿"],
        "generated_on": "2026-09-13",
    },
    {
        "heading": "Article 46 工具为什么有法律牙齿",
        "path": "contrasts/Article 46 工具为什么有法律牙齿.md",
        "type": "contrast",
        "id": "CONTRAST-ARTICLE46-LEGAL-TEETH",
        "aliases": ["GDPR46", "GDPR40(3)", "GDPR42(2)", "GDPR42(4)", "GDPR46(2)(e)", "GDPR46(2)(f)", "ARTICLE42-CERTIFICATION-VS-DPF"],
        "links": ["国际传输三道门与 Article 6 双许可证", "Article 45 — Adequacy decision", "SCC — 第三国法律与履约评估", "Article 47 — Binding Corporate Rules", "教材 §13.2.3 — Codes of conduct, certificates, seals, and marks"],
        "generated_on": "2026-09-13",
    },
]


def extract(text: str, heading: str) -> str:
    pattern = rf"^## 笔记 \d+｜{re.escape(heading)}\n(.*?)(?=^## 笔记 |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f"structured note missing: {heading}")
    return match.group(1).rstrip()


def render(spec: dict, body: str) -> str:
    alias_lines = "\n".join(f'  - "{alias}"' for alias in spec["aliases"])
    link_lines = "\n".join(f"- [[{link}]]" for link in spec["links"])
    if spec["type"] == "rule" and spec.get("summary"):
        quoted = "\n".join(f"> {line}" if line else ">" for line in body.splitlines())
        display_body = (
            f"## 先记住\n\n{spec['summary']}\n\n"
            "> [!note]- 展开完整笔记\n>\n"
            f"{quoted}"
        )
    else:
        display_body = body
    return (
        "---\n"
        f"type: {spec['type']}\n"
        f"id: {spec['id']}\n"
        f'title: "{Path(spec["path"]).stem}"\n'
        "generated: true\n"
        f"generated_on: {spec.get('generated_on', '2026-09-12')}\n"
        "authority_status: derived_from_reviewed_note\n"
        "review_status: current\n"
        "source_refs:\n"
        '  - "08-CIPPE结构化记忆笔记.md"\n'
        "ref_aliases:\n"
        f"{alias_lines}\n"
        "---\n\n"
        f"# {spec['heading']}\n\n{display_body}\n\n"
        "## Wiki 关联\n\n"
        f"{link_lines}\n"
    )


def write_if_changed(path: Path, content: str) -> bool:
    normalized = content.rstrip() + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == normalized:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized, encoding="utf-8")
    return True


def preserve_history_block(path: Path, content: str) -> str:
    if not path.exists():
        return content
    existing = path.read_text(encoding="utf-8")
    match = re.search(re.escape(HISTORY_START) + r".*?" + re.escape(HISTORY_END), existing, re.DOTALL)
    if not match:
        return content
    return f"{content.rstrip()}\n\n{match.group(0)}\n"


def update_home() -> bool:
    home = WIKI / "HOME.md"
    text = home.read_text(encoding="utf-8")
    links = "\n".join(f"- [[{Path(spec['path']).stem}]]" for spec in SPECS)
    block = f"{HOME_START}\n\n## 结构化知识地图\n\n{links}\n\n{HOME_END}"
    if HOME_START in text and HOME_END in text:
        updated = re.sub(re.escape(HOME_START) + r".*?" + re.escape(HOME_END), block, text, flags=re.DOTALL)
    else:
        updated = text.replace("\n## 维护规则", f"\n{block}\n\n## 维护规则")
    return write_if_changed(home, updated)


def project() -> dict:
    source_text = SOURCE.read_text(encoding="utf-8")
    changed = []
    fingerprints = {}
    for spec in SPECS:
        body = extract(source_text, spec["heading"])
        fingerprints[spec["id"]] = hashlib.sha256(body.encode("utf-8")).hexdigest()
        target = WIKI / spec["path"]
        if write_if_changed(target, preserve_history_block(target, render(spec, body))):
            changed.append(spec["path"])
    state = {"schema_version": 1, "source": SOURCE.name, "fingerprints": fingerprints}
    write_if_changed(STATE, json.dumps(state, ensure_ascii=False, indent=2))
    history = build_history_backlinks()
    for page in history["changed_pages"]:
        if page not in changed:
            changed.append(page)
    navigation = build_rule_navigation(WIKI)
    for page in navigation["changed_pages"]:
        if page not in changed:
            changed.append(page)
    return {
        "status": "updated" if changed else "no-op",
        "changed_pages": changed,
        "page_count": len(SPECS),
        "rule_navigation": navigation,
        "history_backlinks": history,
    }


if __name__ == "__main__":
    print(json.dumps(project(), ensure_ascii=False, indent=2))
