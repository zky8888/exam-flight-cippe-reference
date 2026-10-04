# 建立可追溯、可重建的 CIPP/E Obsidian Wiki

> 文件位置：`iterations/v1-obsidian-wiki/.plan/plan.md`
> 配套 skill：first-flight-phases
> 本 plan 文档是稳定航图；状态跟踪在 `phases/` 中。

## 背景

现有项目已经保存教材、题库、法律核验、结构化记忆、错题、复习调度和学习事件，但同一知识对象分散在多种文件中。目标不是重写这些来源，而是生成一套 Obsidian 可浏览的知识投影，把规则、主体、题目、个人错因和学习证据连接起来。投影必须可重复生成，并且不得反向覆盖权威数据或学习历史。

## 范围

**做：**

- 为 DPO、DPA、Article 78、Article 83 原型定义领域模型和稳定 ID。
- 从既有 Markdown、JSON 和 SQLite 生成只读 Wiki 页面。
- 在 Obsidian 中验证首页、双链、局部图谱和来源回溯。
- 建立增量检测以及自动更新、候选评审、禁止更新三类策略。

**不做：**

- 不修改原始教材、题库、错题、作答、复习或掌握记录。
- 不让 AI 修改 verified answer、verification status、题源真实性或 S3/S4 状态。
- 不在首轮覆盖全部 307 题，也不安装第三方 Obsidian 插件。
- 不自动联网生成或采纳法律结论。

## 阶段总览

| # | 阶段 slug | 一句话目标 | 状态 |
|---|---|---|---|
| 01 | knowledge-model | 定义知识对象、稳定 ID、来源和写入边界 | completed |
| 02 | prototype-generator | 生成监管责任簇首批页面并验证幂等性 | completed |
| 03 | obsidian-validation | 在 Obsidian 验证导航、双链和图谱 | completed |
| 04 | incremental-maintenance | 根据来源变化只更新受影响的投影 | completed |
| 05 | safety-review | 验证自动更新与人工评审边界 | completed |
| 06 | holdout-evaluation | 用两个未参与规则设计的真实案例验证陌生输入处理 | completed |
| 07 | conversation-intake | 把自然语言错题分析转换成受控 Wiki 更新候选 | completed |
| 08 | hot-context | 用每日热上下文替代启动时全量读取不断增长的历史文件 | completed |
| 09 | object-index | 用轻量对象索引支持增量同步和已有页面自动链接 | completed |
| 10 | index-auto-refresh | 同步前轻量检测页面结构变化并按需刷新对象索引 | completed |
| 11 | structured-note-projection | 将已审核的结构化记忆笔记投影为实质 Wiki 主题页 | completed |
| 12 | rule-first-navigation | 将 Wiki 首页重构为会随规则页自动生长的规则优先入口 | completed |
| 13 | history-coverage-audit | 盘点全部已保存错题与对话事件相对规则 Wiki 的覆盖缺口 | completed |
| 14 | history-rule-backlinks | 将历史错题和对话事件安全地反向链接到已有规则 | completed |
| 15 | semantic-impact-sync | 让未来 Wiki 同步自动判断新增、补充、冲突与旧页影响 | completed |
| 16 | learner-facing-slimdown | 分离学习入口与维护后台，压缩首页、目录和规则页视觉复杂度 | completed |

## 关键决策

- **2026-09-11**：现有 SQLite、JSON 和学习文件继续作为真相源；`wiki/` 只是可删除重建的投影。
- **2026-09-11**：Obsidian 负责浏览和人工检查，自动维护在项目脚本与受控 AI 流程中完成。
- **2026-09-11**：首个原型限定在 DPO—DPA—Article 78—Article 83，避免全库导入后难以判断实际收益。
- **2026-09-11**：学习事件不可变；稳定知识可生成候选更新；权威结论不得自动写回。
- **2026-09-12**：用 TQ-241 与 TQ-060-retest 做首轮工程留出测试；测试输入和人工验收答案分离保存，Agent 不读取答案文件。
- **2026-09-12**：自然语言层采用“项目 Skill 负责语义抽取、确定性脚本负责校验和动作分层”的组合；不要求安装 LLM Wiki App。
- **2026-09-12**：每日任务采用热/温/冷三层读取；启动只加载自动生成的当前快照和强制协议，完整历史按具体题目调用。
- **2026-09-12**：Wiki 全库扫描只用于重建对象索引；日常对话同步只读取索引、候选和审核队列。
- **2026-09-12**：对象索引使用页面路径、大小和修改时间检测过期；仅在签名变化时读取 frontmatter 重建。
- **2026-09-12**：用户确认将今日结构化笔记 008–012 作为已审核来源投影到 Wiki；页面保留原文并只增加导航关系。
- **2026-09-13**：Wiki 主导航改为规则优先；所有 `type: rule` 页必须自动进入规则目录，无法分类时进入“待归类”而不得隐身。
- **2026-09-13**：历史回填先做覆盖审计，再生成反向链接；没有稳定来源支撑的历史标签不得直接升级为正式法律规则。
- **2026-09-13**：每次对话入库必须输出语义影响处置；仅无知识变化的证据链接可自动完成，规则补充、边界、例外、新规则、冲突和未解析引用均进入评审。
- **2026-09-14**：Wiki 默认界面只服务日常学习；工程报告、对象索引和维护入口不再出现在首页。历史数据保留，但以折叠证据呈现。

## Open Questions

- [x] Obsidian 图谱是否需要颜色和分组插件 — Phase 03 已用原生五组颜色完成，无需插件。
- [x] 是否需要向量语义搜索 — 当前 38 页暂不需要；出现真实检索失败或约 200 页以上时重评。
- [ ] 是否建立不含答案的 Learner Wiki — 不属于本轮原型，需后续单独立项。

## 关联

- [项目入口](../../../AGENTS.md)
- [知识库与调用协议](../../../06-CIPPE知识库与调用协议.md)
- [教材优先与题库调用协议](../../../knowledge_base/article_map/教材优先与题库调用协议.md)
- [Wiki 模型](../../../wiki/_meta/SCHEMA.md)
- [写入边界](../../../wiki/_meta/WRITEBACK_POLICY.md)
