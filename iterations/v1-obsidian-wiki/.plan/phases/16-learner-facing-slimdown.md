# Phase 16 — 学习界面瘦身

**Status**: `completed`
**目标**: 将日常学习入口与工程维护后台分离，让用户主要沿“规则 → 错题/事件证据”浏览。
**前置**: Phase 15 已完成语义影响同步。

## 验收判据

- HOME 从 7 类入口压缩为规则目录、错题复习和简短使用说明。
- RULES 不再只是标题列表；每条规则显示一句摘要、错题数、事件数和待审核更新数。
- 规则页的历史证据默认折叠，不再用多个展开章节打断正文。
- 详细结构化规则笔记默认折叠，同时保留完整原文与来源。
- 后台页面不删除，但不再出现在日常主导航；生成器重复运行不会恢复旧的繁杂首页。

## Tasks

- [x] 重构 HOME 为极简学习入口。（`wiki/scripts/build_rule_navigation.py:139`；`wiki/HOME.md:13`）
- [x] 将 RULES 改为带摘要和关联数量的高信息密度目录。（`wiki/scripts/build_rule_navigation.py:28`；`wiki/RULES.md:14`）
- [x] 折叠规则详情和历史证据，保留完整内容。（`wiki/scripts/project_structured_notes.py:111`；`wiki/scripts/build_history_backlinks.py:118`）
- [x] 清除旧生成器对首页的重复注入。（`wiki/scripts/project_structured_notes.py:159`；`wiki/scripts/sync_wiki.py:239`；`wiki/scripts/build_pilot.py:319`）
- [x] 更新测试并完成全库校验。（`wiki/tests/test_rule_navigation.py:52`；`wiki/tests/test_structured_note_projection.py:43`；38 tests OK；投影 60/60 且无失效双链；Obsidian 阅读视图实测通过）

## Notes

- 2026-09-14：瘦身采用“隐藏后台、折叠详情、保留数据”，不物理删除历史页面。
- 2026-09-14：HOME 从 34 个 Wiki 链接压缩为 2 个，正文约 620 字符；RULES 的 10 条规则均显示摘要与三项关联数量。
- 2026-09-14：Obsidian 已切换阅读视图并收起文件树；长规则仅显示“先记住”、相关规则和折叠证据，完整笔记仍可展开。
