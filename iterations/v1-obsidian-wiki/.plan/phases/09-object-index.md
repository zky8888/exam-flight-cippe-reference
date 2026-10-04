# Phase 09 — Wiki 对象索引

**Status**: `completed`
**目标**: 让日常同步无需读取全部 Wiki，即可识别并连接已有对象。
**前置**: 用户确认建立轻量 Wiki 对象索引。

## 验收判据

- 索引重建只读取 Wiki 页面 frontmatter，不把正文交给同步 Agent。
- 索引包含稳定 ID、类型、页面路径、wikilink 标题和明确 ref aliases。
- 日常候选处理只读取对象索引，不使用写死的规则页面映射。
- 已有对象自动链接；未知对象保持 Review Inbox，不自动创建法律结论。
- 重新处理最近两个事件后，BCR/SA 事件实际显示已有监管机关链接，未知 SCC/BCR 规则仍待审核。

## Tasks

- [x] 为现有核心规则和主体补充明确引用别名。（`wiki/rules/Article 14(3) — 间接取得数据的告知时点.md:8`；`wiki/actors/Supervisory Authority.md:8`）
- [x] 实现对象索引生成器并生成索引。（`wiki/scripts/build_object_index.py:17-94`；`wiki/_state/object-index.json`）
- [x] 将对话候选处理器改为索引解析。（`wiki/scripts/process_conversation_candidate.py:51-70,96-143`）
- [x] 重放最近两个同步事件并核对链接和审核状态。（`wiki/learning-events/LE-TQ-065-20260912.md`；`wiki/learning-events/LE-CLAR-20260912-BCR-SA-ROLES.md:14`）
- [x] 增加索引唯一性、未知对象和幂等性测试。（`wiki/tests/test_object_index.py:1`；18 项合并测试通过；索引连续重建 SHA-256 一致）

## Notes

- 2026-09-12：最近两次同步均成功写入学习事件；TQ-065 的 SCC 对象尚不存在，BCR/SA 事件虽批准主体链接但页面尚未实际呈现，说明索引解析是下一必要步骤。
- 2026-09-12：索引收录 43 个对象、15 个明确引用别名，文件约 16.7 KB；普通同步仅读取该索引，不扫描页面正文。
- 2026-09-12：BCR/SA 事件现已实际连接 `[[Supervisory Authority]]`；SCC、BCR approval 等尚无稳定页面的引用继续进入 Review Inbox。
- 2026-09-12：所有真相源文件指纹不变；43 个 Wiki 页面、43 个唯一 ID、0 个失效链接；个人同步 Skill 已补充索引重建时机并通过格式校验。
