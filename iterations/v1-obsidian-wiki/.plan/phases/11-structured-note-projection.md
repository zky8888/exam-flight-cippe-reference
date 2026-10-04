# Phase 11 — 结构化笔记实质投影

**Status**: `completed`
**目标**: 将 `08-CIPPE结构化记忆笔记.md` 中已审核的今日笔记 008–012 生成为可直接阅读的 Wiki 主题页。
**前置**: 用户已确认将审核队列中的稳定笔记正式投影。

## 验收判据

- 产生五张有完整正文的主题页，不再只有事件摘要。
- 每页具有稳定 ID、来源、别名和明确的相互关联。
- Wiki 首页出现“2026-09-12 知识地图”入口。
- 重复运行无变化，结构化笔记更新时只更新对应页。
- 对象索引自动刷新，Wiki 零断链，受保护原始来源不变。

## Tasks

- [x] 实现按稳定标题抽取笔记切片的确定性投影器。（`wiki/scripts/project_structured_notes.py:19-132`）
- [x] 生成边界、机构、Adequacy、SCC 和 BCR 五张主题页。（`python3 wiki/scripts/project_structured_notes.py`：`page_count: 5`）
- [x] 在 HOME 中增加今日知识地图并建立双链。（`wiki/HOME.md:60-70`）
- [x] 验证增量幂等、自动索引、零断链与真相源不变。（`python3 -m unittest discover -s wiki/tests -p 'test_*.py' -v`：25 tests OK；`validate_projection.py`：48 pages / 0 dead links；二次投影 `no-op`；7 个真相源 SHA-256 一致）

## Notes

- 2026-09-12：此阶段修复“学习事件已入库，但稳定笔记没有变成 Wiki 主题页”的管道缺口。
- 2026-09-12：索引自动检测到 6 个稳定页面变化并重建；TQ-065、BCR、Councils 和 Article 83 事件已连到新主题页。
