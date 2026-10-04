# Phase 15 — 语义影响同步

**Status**: `completed`
**目标**: 让每次对话候选在写入 Wiki 时，明确判断对既有规则页的影响和安全动作层级。
**前置**: Phase 14 已完成历史反向链接。

## 验收判据

- 六种知识影响均转换成稳定、可解释的处置结果。
- 学习事件页显示“对旧页面的影响”，区分自动证据链接、旧页补充评审、新规则评审和冲突评审。
- 形成去重的语义影响台账与可读报告。
- 全部现有 inbox 候选完成回填，重复运行不产生重复项。
- 正式规则正文、原始答案和掌握状态不被未经审核地修改。

## Tasks

- [x] 实现知识影响决策器和动作分层。（`wiki/scripts/process_conversation_candidate.py:19`；`wiki/scripts/process_conversation_candidate.py:84`）
- [x] 将影响结果写入事件页、JSON 台账和可读报告。（`wiki/scripts/process_conversation_candidate.py:120`；`wiki/scripts/process_conversation_candidate.py:130`；`wiki/reports/semantic-impact.md:1`）
- [x] 回填现有候选并接入完整同步流程。（`wiki/review/semantic-impact.json`；`AGENTS.md:10`；`06-CIPPE知识库与调用协议.md:291`；`~/.codex/skills/cippe-wiki-sync/SKILL.md:24`）
- [x] 增加六类影响、去重与安全边界测试并完成全库校验。（`wiki/tests/test_conversation_candidate.py:39`；35 tests OK；12 个候选重复处理后台账指纹不变；投影 60/60 且无失效双链）

## Notes

- 2026-09-13：AI 负责产生候选语义；确定性程序负责校验、分层和阻止越权写入。
- 2026-09-13：现有 12 个候选已回填；11 个进入既有页面补充评审，1 个进入新规则/别名评审。没有规则正文被候选直接覆盖。
- 2026-09-13：规则首页和总目录已增加语义影响报告入口；Skill frontmatter 与 JSON 台账校验通过。
