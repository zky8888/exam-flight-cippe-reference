#!/usr/bin/env python3
"""Build a compact daily context from append-only CIPP/E learning sources."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


MAX_OUTPUT_CHARS = 12_000


def load_coverage_module(root: Path):
    path = root / "scripts" / "original_question_coverage.py"
    spec = importlib.util.spec_from_file_location("original_question_coverage", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def latest_section(text: str, heading_pattern: str, cap: int) -> str:
    matches = list(re.finditer(heading_pattern, text, re.MULTILINE))
    if not matches:
        return "（未找到当前段落，请按需查看来源文件。）"
    start = matches[-1].start()
    level = len(matches[-1].group(1))
    following = re.search(rf"^#{{1,{level}}}\s+", text[matches[-1].end():], re.MULTILINE)
    end = matches[-1].end() + following.start() if following else len(text)
    section = text[start:end].strip()
    return section if len(section) <= cap else section[:cap].rstrip() + "\n\n…（其余内容按需读取来源文件）"


def recent_misconceptions(text: str, limit: int = 6) -> str:
    rows = [line for line in text.splitlines() if re.match(r"^\| CIPP-\d+", line)]
    compact = []
    for row in rows[-limit:]:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) < 4:
            continue
        item = cells[0]
        topic = cells[2]
        status = cells[-2] if len(cells) >= 2 else ""
        next_date = cells[-1]
        compact.append(f"- `{item}`：{topic[:90]}；状态：{status[:45]}；下次：{next_date[:20]}")
    return "\n".join(compact) or "- 暂无可提取记录。"


def recent_events(path: Path, limit: int = 8) -> str:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))[-limit:]
    output = []
    for row in rows:
        key = row.get("event_key") or row.get("question_id") or "unknown"
        correct = row.get("is_correct") or row.get("correct") or "unknown"
        code = row.get("error_code") or row.get("misconception_code") or "—"
        note = row.get("notes") or row.get("note") or ""
        output.append(f"- `{key}`：correct={correct}；错因={code}；{note[:150]}")
    return "\n".join(output)


def build(root: Path) -> str:
    generated = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
    dashboard = read(root / "00-CIPPE总控台.md")
    queue = read(root / "02-间隔复习队列.md")
    daily = read(root / "03-每日学习记录.md")
    mistakes = read(root / "01-错题库.md")
    coverage_module = load_coverage_module(root)
    coverage = coverage_module.build_inventory(root)
    coverage_module.write_outputs(coverage, root)
    coverage_summary = coverage["summary"]
    unseen_candidates = coverage_module.select_candidates(coverage, limit=5)
    candidate_text = "、".join(row["question_id"] for row in unseen_candidates) or "暂无"
    parts = [
        "# CIPP/E 今日热上下文",
        "",
        f"> 自动生成：{generated}（Asia/Shanghai）。这是导航快照，不是真相源；每次晨学开始先重新生成。",
        "",
        "## 使用规则",
        "",
        "- 默认只用本页确定今日入口；涉及具体题目时，再读取对应教材正文、题库记录和 Wiki 页面。",
        "- 不因本页摘要自动升级掌握度，不用摘要替代答案核验或来源核验。",
        "- 完整来源：[[00-CIPPE总控台]]、[[01-错题库]]、[[02-间隔复习队列]]、[[03-每日学习记录]]、[[07-IAPP-BOK覆盖矩阵]]。",
        "",
        "## 当前主线",
        "",
        latest_section(dashboard, r"^(##)\s+\d{4}-\d{2}-\d{2}.*状态同步快照.*$", 1_800),
        "",
        "## 最新复习调度",
        "",
        latest_section(queue, r"^(##)\s+\d{4}-\d{2}-\d{2}.*$", 2_800),
        "",
        "## 最近学习闭环",
        "",
        latest_section(daily, r"^(#{2,3})\s+\d{4}-\d{2}-\d{2}.*$", 1_500),
        "",
        "## 最近六个错因条目",
        "",
        recent_misconceptions(mistakes),
        "",
        "## 最近八个学习事件",
        "",
        recent_events(root / "10-逐题作答记录.csv"),
        "",
        "## 307题原题覆盖",
        "",
        f"- 已真实作答：**{coverage_summary['attempted']} / {coverage_summary['total']}**"
        f"（{coverage_summary['original_coverage_percent']}%）；已核验但未做："
        f"**{coverage_summary['ready_unseen']}**；待审核：**{coverage_summary['needs_audit']}**；"
        f"暂停：**{coverage_summary['blocked']}**。",
        f"- 全库下一批可用未做原题（教师候选）：{candidate_text}。实际出题应先按当日 BoK/概念筛选，并运行 `--prepare`。",
        "",
        "## 按需读取入口",
        "",
        "- 判题/讲解：先读 `06-CIPPE知识库与调用协议.md` 与 `knowledge_base/article_map/教材优先与题库调用协议.md`，再调用具体教材段落。",
        "- 到期安排不清：打开 `02-间隔复习队列.md`；错因细节不清：打开 `01-错题库.md`。",
        "- 查询关系：打开 `wiki/HOME.md`；查询原题：使用 `knowledge_base/article_map/query_question_map.py --question N --prepare`。",
        "- 每日原题候选：使用 `scripts/original_question_coverage.py --select --bok III.D --limit 3`；不得用“知识点已教”代替“原题已作答”。",
        "",
    ]
    result = "\n".join(parts)
    if len(result) > MAX_OUTPUT_CHARS:
        raise ValueError(f"CURRENT-CONTEXT exceeds {MAX_OUTPUT_CHARS} chars: {len(result)}")
    return result


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=root / "CURRENT-CONTEXT.md")
    args = parser.parse_args()
    content = build(root)
    args.output.write_text(content, encoding="utf-8")
    print(f"Wrote {args.output}: {len(content)} chars")


if __name__ == "__main__":
    main()
