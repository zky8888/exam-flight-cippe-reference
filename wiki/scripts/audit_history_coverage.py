#!/usr/bin/env python3
"""Audit saved learning history against the current rule-first Wiki."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

from build_object_index import frontmatter, list_values, scalar


ROOT = Path(__file__).resolve().parents[2]
WIKI = ROOT / "wiki"
REPORT = WIKI / "reports" / "history-coverage.md"


def article_numbers(value: str) -> set[str]:
    found = set(re.findall(r"(?:GDPR|Article)\s*([0-9]{1,2})", value, re.I))
    for start, end in re.findall(r"GDPR\s*([0-9]{1,2})\s*[-–]\s*([0-9]{1,2})", value, re.I):
        found.update(str(number) for number in range(int(start), int(end) + 1))
    if re.search(r"GDPR\s*[0-9]", value, re.I):
        found.update(re.findall(r";\s*([0-9]{1,2})(?=\s*(?:\(|;|$))", value))
    return found


def legal_refs(value: str) -> set[str]:
    """Keep identically numbered articles from different laws in separate namespaces."""
    refs: set[str] = set()
    for match in re.finditer(r"\b(GDPR|AI\s*Act|AIAct)\s*(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?", value, re.I):
        law = "AIACT" if re.sub(r"\s+", "", match.group(1)).upper() == "AIACT" else "GDPR"
        start = int(match.group(2))
        end = int(match.group(3)) if match.group(3) else start
        refs.update(f"{law}:{number}" for number in range(start, end + 1))
    if re.search(r"\bGDPR\s*\d", value, re.I):
        refs.update(f"GDPR:{number}" for number in re.findall(r";\s*([0-9]{1,2})(?=\s*(?:\(|;|$))", value))
    if re.search(r"\b(?:AI\s*Act|AIAct)\s*Annex\s*III\b|\bAIACTANNEXIII\b", value, re.I):
        refs.add("AIACT:ANNEXIII")
    return refs


def rule_inventory() -> tuple[dict[str, str], dict[str, set[str]]]:
    titles: dict[str, str] = {}
    articles: dict[str, set[str]] = {}
    for path in sorted((WIKI / "rules").glob("*.md")):
        meta = frontmatter(path)
        if meta is None or scalar(meta, "type") != "rule":
            continue
        title = scalar(meta, "title") or path.stem
        aliases = " ".join(list_values(meta, "ref_aliases"))
        titles[path.stem] = title
        articles[path.stem] = legal_refs(f"{path.stem} {title} {aliases}")
    return titles, articles


def cipp_ids(text: str) -> set[str]:
    return set(re.findall(r"\|\s*(CIPP-[0-9]{3})\s*\|", text))


def write_if_changed(path: Path, content: str) -> bool:
    normalized = content.rstrip() + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == normalized:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized, encoding="utf-8")
    return True


def audit() -> dict:
    with (ROOT / "10-逐题作答记录.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    wrong = [row for row in rows if row.get("correct", "").lower() == "false"]
    rules, rule_articles = rule_inventory()

    refs = Counter()
    matched = Counter()
    unmatched = Counter()
    for row in rows:
        raw = row.get("rule", "").strip()
        if not raw:
            continue
        refs[raw] += 1
        numbers = legal_refs(raw)
        hits = [stem for stem, present in rule_articles.items() if numbers & present]
        if hits:
            for stem in hits:
                matched[stem] += 1
        else:
            unmatched[raw] += 1

    wrong_text = (ROOT / "01-错题库.md").read_text(encoding="utf-8")
    daily_text = (ROOT / "03-每日学习记录.md").read_text(encoding="utf-8")
    notes_text = (ROOT / "08-CIPPE结构化记忆笔记.md").read_text(encoding="utf-8")
    inbox = list((WIKI / "inbox").glob("*.json"))
    events = list((WIKI / "learning-events").glob("*.md"))
    note_headings = re.findall(r"^## 笔记\s+\d+｜(.+)$", notes_text, re.M)
    answer_event_count = len({row["question_id"] for row in rows})
    wrong_event_count = len({row["question_id"] for row in wrong})
    daily_tq_count = len(set(re.findall(r"TQ[- #]*(\d{1,3})", daily_text)))

    matched_lines = [
        f"- [[{stem}]]：{matched.get(stem, 0)} 条作答记录存在 Article 级导航命中"
        for stem in sorted(rules)
    ]
    missing_lines = [
        f"- `{name}`：{count} 条记录"
        for name, count in unmatched.most_common()
    ] or ["- 无"]

    content = f'''---
type: report
id: REPORT-HISTORY-COVERAGE
title: "历史学习记录—规则 Wiki 覆盖审计"
generated: true
generated_on: 2026-09-13
source_refs:
  - "01-错题库.md"
  - "03-每日学习记录.md"
  - "08-CIPPE结构化记忆笔记.md"
  - "10-逐题作答记录.csv"
---

# 历史学习记录—规则 Wiki 覆盖审计

> [!important] 口径
> “导航命中”只表示作答记录中的显式 Article 编号能找到现有规则页，不表示答案、规则表述或掌握状态已经核验。

## 历史规模

| 来源 | 已保存内容 |
|---|---:|
| 逐题作答记录 | {len(rows)} 条、{answer_event_count} 个事件键 |
| 其中明确答错 | {len(wrong)} 条、{wrong_event_count} 个事件键 |
| 错题库稳定错因 ID | {len(cipp_ids(wrong_text))} 个 |
| 每日记录中出现的 TQ 引用 | {daily_tq_count} 个题号 |
| 已审核结构化笔记 | {len(note_headings)} 节 |
| Wiki inbox 候选 | {len(inbox)} 个 |
| 已投影对话/学习事件 | {len(events)} 个 |
| 当前正式规则页 | {len(rules)} 个 |

## 已有规则页的历史命中

{chr(10).join(matched_lines)}

## 尚无对应正式规则页的显式规则标签

以下标签来自作答记录，下一阶段必须结合错题库、结构化笔记及已核验来源判断是新建规则、归并别名，还是仅保留为待审核关系：

{chr(10).join(missing_lines)}

## 下一阶段回填顺序

1. 先处理明确答错的 {len(wrong)} 条记录，把题目、错因和已有规则页连接起来。
2. 再处理答对但理由不完整、低信心或 guided repair 的记录。
3. 对尚无规则页的标签，只生成候选；经已有结构化笔记或权威来源支持后才建立正式规则页。
4. 将现有 {len(events)} 个对话事件反向显示在相关规则页，保留事件不可变性。
'''
    changed = write_if_changed(REPORT, content)
    return {
        "status": "updated" if changed else "no-op",
        "report": str(REPORT.relative_to(ROOT)),
        "answer_rows": len(rows),
        "wrong_rows": len(wrong),
        "cipp_ids": len(cipp_ids(wrong_text)),
        "structured_notes": len(note_headings),
        "wiki_events": len(events),
        "rule_pages": len(rules),
        "distinct_rule_labels": len(refs),
        "unmatched_rule_labels": len(unmatched),
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
