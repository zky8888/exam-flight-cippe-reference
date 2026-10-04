# Phase 07 — 对话事件入口

**Status**: `completed`
**目标**: 让本项目中的 AI 把自然语言错题分析转换为结构化候选，再交给确定性安全门处理。
**前置**: Phase 06 完成并经用户验收。

## 验收判据

- 项目内有可重复调用的 Wiki 同步 Skill，并能被其他对话发现。
- 自然语言抽取结果保留原文证据，不确定字段显式标 unknown，不补造法律结论。
- 候选 JSON 必须通过 schema、安全动作和重复事件校验才能进入 Review Inbox。
- 用本项目真实 Article 14/36 对话片段完成一次端到端演示。
- 原始学习记录不变；所有语义更新仍需人工审核。

## Tasks

- [x] 创建项目级 Wiki 同步 Skill 与抽取协议。（`~/.codex/skills/cippe-wiki-sync/SKILL.md:1`；`references/intake-schema.md:1`）
- [x] 实现候选事件校验及 Review Inbox 合并器。（`wiki/scripts/process_conversation_candidate.py:25`；`wiki/review/conversation-pending.json:1`）
- [x] 把 Skill 接入项目 AGENTS 入口。（`AGENTS.md:10`）
- [x] 用真实自然语言片段完成端到端演示。（`wiki/inbox/CLAR-20260911-ART14-36.json:1`；`wiki/learning-events/LE-CLAR-20260911-ART14-36.md:1`）
- [x] 运行 Skill、脚本、安全边界和原始文件不变验证。（`python3 -m unittest wiki/tests/test_safety_review.py wiki/tests/test_holdout_classifier.py wiki/tests/test_conversation_candidate.py`；`python3 wiki/scripts/validate_projection.py`；Skill `quick_validate.py`）

## Notes

- 2026-09-12：用户确认继续实现“自由文本对话 → 结构化学习事件 → Wiki 安全更新”入口。
- 2026-09-12：个人 Skill `cippe-wiki-sync` 安装并通过格式校验；项目 AGENTS 已加入触发路由，其他备考对话可在用户要求同步时调用。
- 2026-09-12：真实 Article 14/36 对话片段成功生成第 39 个 Wiki 页面；2 个动作自动执行，1 个错因合并建议进入审核，0 个越权动作。
- 2026-09-12：重复处理同一 event key 返回 `already_processed`，页面及六个真相源文件指纹不变；共 9 项测试通过，39 个 Wiki ID 唯一且 0 个失效链接。
