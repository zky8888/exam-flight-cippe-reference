# Phase 05 — 安全评审

**Status**: `completed`
**目标**: 验证自动更新、候选建议和禁止写回的边界能够持续执行。
**前置**: Phase 04 完成并经用户验收。

## 验收判据

- 低风险链接和索引变化可以自动更新。
- 语义归类和规则补充写入 Review Inbox，不覆盖稳定知识。
- verified answer、核验状态、题源真实性、S3/S4 修改被拒绝。
- 输出一份可读的维护报告，区分已处理、待评审和已阻止。

## Tasks

- [x] 实现三层动作分类器。
- [x] 生成 Review Inbox。
- [x] 增加受保护字段回归检查。
- [x] 验证冲突不会写回真相源。
- [x] 评估是否需要语义搜索或定时自动化。
- [x] 建立 6–10 个多类型真实案例的标注与评测包（added 2026-09-12: 用户确认以真实案例打磨通用规则，不训练新模型）。

## Notes

- 2026-09-12：Phase 04 经用户确认通过；开始安全分类与小样本通用化。
- 2026-09-12：建立 `CLASSIFICATION_SCHEMA.json` 与 8 个真实案例的 `CASEBOOK.json`；覆盖期限迁移、角色权限膨胀、触发条件、知识缺口、污染作答、题源冲突、可能错因合并和 guided repair。
- 2026-09-12：24 个动作断言全部通过：7 个允许自动处理、8 个进入 Review Inbox、9 个受保护动作被阻止；4 项回归测试通过。
- 2026-09-12：运行前后 6 个真相源文件 SHA-256 完全一致；投影校验为 38 页、38 个唯一 ID、0 个失效链接。
- 2026-09-12：当前暂缓语义搜索和无人值守定时写入；先用手动触发，并要求至少 2 个未参与设计的新案例通过后再升级自动化。

## Evidence

- 分类规则：`wiki/agent/CLASSIFICATION_SCHEMA.json`
- 真实案例：`wiki/agent/CASEBOOK.json`
- 待审核清单：`wiki/review/pending.json`
- 可读报告：`wiki/reports/latest.md`
- 自动化决策：`wiki/_meta/AUTOMATION_DECISION.md`
- 验证命令：`python3 wiki/scripts/safety_review.py && python3 wiki/scripts/validate_projection.py && python3 -m unittest wiki/tests/test_safety_review.py`
