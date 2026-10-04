# Phase 06 — 陌生案例留出测试

**Status**: `completed`
**目标**: 验证 Agent 能否把未参与原规则设计的真实学习事件转换成安全、可审核的 Wiki 维护建议。
**前置**: Phase 05 完成并经用户验收。

## 验收判据

- 两个案例均未出现在原 8 案例 CASEBOOK 中。
- 测试输入不包含预期分类，人工验收答案单独冻结。
- Agent 输出事件类型、知识影响、错因影响和动作分层，并说明证据。
- 自动动作仅触及 Wiki；语义动作进入 Review Inbox；掌握状态修改被阻止。
- 运行前后原始学习文件不变，既有 Wiki 校验继续通过。

## Tasks

- [x] 冻结两个留出案例的输入与人工验收答案。（`wiki/agent/HOLDOUT_INPUTS.json:1`；`wiki/agent/HOLDOUT_GOLD.json:1`）
- [x] 实现陌生学习事件分类器与解释输出。（`wiki/scripts/classify_learning_event.py:13`）
- [x] 运行留出评测并生成可读报告。（`wiki/reports/holdout-evaluation.md:1`；`python3 wiki/scripts/evaluate_holdout.py`）
- [x] 验证原始文件不变及 Wiki 链接完整。（六个真相源 SHA-256 前后一致；`python3 wiki/scripts/validate_projection.py`）

## Notes

- 2026-09-12：用户确认开始两个新案例实战盲测。
- 2026-09-12：选择 `TQ-241`（首次作答、新错因）与 `TQ-060-retest`（正确回测、规则仍不完整）；二者均未进入 Phase 05 的 8 案例评测包。
- 2026-09-12：两个留出案例共 13 项分类断言全部通过；合并测试共 6 项通过；Wiki 仍为 38 页、38 个唯一 ID、0 个失效链接。
- 2026-09-12：本轮验证的是“结构化学习事件 → 安全维护建议”，尚未验证从自由文本对话自动抽取结构化字段。
