# Phase 04 — 增量维护

**Status**: `completed`
**目标**: 检测来源变化，并只重建受到影响的 Wiki 投影。
**前置**: Phase 03 完成并经用户验收。

## 验收判据

- 保存来源哈希和生成清单。
- 无来源变化时运行结果明确为 no-op。
- 新增测试学习事件时，只更新对应事件、规则、错因和索引页面。
- 删除测试输入后可恢复到原状态，不遗留死链。

## Tasks

- [x] 定义来源指纹和依赖清单（`wiki/scripts/sync_wiki.py:96`；持久状态见 `wiki/_state/manifest.json:1`）。
- [x] 实现变化检测（相关 CSV 事件、结构化笔记切片、题目行和教材小节分别指纹；`wiki/scripts/sync_wiki.py:53`、`wiki/scripts/sync_wiki.py:63`、`wiki/scripts/sync_wiki.py:75`）。
- [x] 实现受影响页面选择（TQ-108 profile 只拥有对应来源、规则、题目、错因、对比和事件页面；`wiki/scripts/sync_wiki.py:125`、`wiki/_state/manifest.json:15`）。
- [x] 实现变更摘要（同步命令返回 `updated` / `state-only` / `no-op` 及 `changed_pages`；`wiki/scripts/sync_wiki.py:270`、`python3 wiki/scripts/sync_wiki.py`）。
- [x] 验证增量更新与恢复（主库第二次运行 `no-op`；临时副本删除事件后 30 页零断链，恢复后 38 页零断链；`python3 wiki/scripts/validate_projection.py`）。

## Notes

- 2026-09-11：用户确认进入增量 Agent 建设；以已落盘但仅部分织入的 TQ-108 为首个真实样本。
- 2026-09-12：Q108 教师准备入口实际读取题目与教材 §8.1.3、§8.1.5；Article 36 对比同时读取教材 §11.5.1.3。
- 2026-09-12：首次同步补齐 10 个受影响页面；兼容另一任务已建立的短文件名 `Article 14与DPIA咨询期限`。
- 2026-09-12：正式源文件哈希复核全部 `OK`；同步器只写 `wiki/` 投影与 `_state/manifest.json`。
