# Phase 14 — 历史错题与规则反向链接

**Status**: `completed`
**目标**: 将已保存的明确错题和 Wiki 学习事件连接到已有规则页，使规则成为历史学习证据的主入口。
**前置**: Phase 13 已完成历史覆盖审计。

## 验收判据

- 22 条明确答错记录全部进入历史错题索引，并保留来源字段。
- 18 个 Wiki 学习事件全部进入事件索引；可识别的规则关系反向显示在规则页。
- 规则页的历史证据区由程序维护且重复执行不产生重复内容。
- 不存在的规则只进入待补规则清单，不自动生成法律结论。
- 全库测试和双链校验通过，原始学习文件不被修改。

## Tasks

- [x] 生成历史错题索引和对话事件索引。（`wiki/history/WRONG-QUESTIONS.md:14`；`wiki/history/CONVERSATION-EVENTS.md:14`）
- [x] 为已有规则页生成受控历史证据反向链接区。（`wiki/scripts/build_history_backlinks.py:118`）
- [x] 将反向链接刷新接入 Wiki 生成流程。（`wiki/scripts/project_structured_notes.py:11`；`wiki/scripts/build_pilot.py:11`；`wiki/scripts/build_rule_navigation.py:89`）
- [x] 增加覆盖完整性与幂等测试并完成全库校验。（`wiki/tests/test_history_backlinks.py:12`；33 tests OK；二次运行 `no-op`；投影 60/60 且无失效双链）

## Notes

- 2026-09-13：链接表示学习关联，不代表答案核验或掌握状态变化。
- 2026-09-13：22 条明确错题全部进入索引，其中 13 条安全连接到现有规则；18 个事件全部进入索引，其中 11 个具有明确规则反向链接。其余项目保持可见但不强行匹配。
- 2026-09-13：完整同步协议和 `$cippe-wiki-sync` 已加入历史反向链接刷新步骤；Skill frontmatter 校验通过，官方 quick validator 因当前 Python 环境缺少 PyYAML 未能运行。
