---
type: wiki_schema
schema_version: 1
status: active
updated_on: 2026-09-11
---

# CIPP/E Wiki 知识模型

## 定位

`wiki/` 是由现有 CIPP/E 数据生成的知识投影，用于 Obsidian 导航、双链和图谱探索。它不是新的答案库，也不是学习记录的真相源。任何生成页都必须能够追溯到现有 Markdown、CSV、JSON 或 SQLite 数据。

## 真相源优先级

1. 原始题面、题库印刷答案和教材正文：`knowledge_base/cippe_kb.sqlite3` 及 article map 导出。
2. 独立法律核验和题目审计：SQLite 中的 verification/audit 字段。
3. 学习事实：`10-逐题作答记录.csv`、`01-错题库.md`、`03-每日学习记录.md`。
4. 当前调度：`02-间隔复习队列.md`。
5. 稳定记忆结构：`08-CIPPE结构化记忆笔记.md`。
6. Wiki 页面：只读投影；与上述来源冲突时不得反向覆盖。

## 页面类型与稳定 ID

### `rule`

- 含义：Article、款项或可独立判断的法律规则。
- ID：`RULE-GDPR-{article}-{slug}`，例如 `RULE-GDPR-38-DPO-POSITION`。
- 路径：`wiki/rules/`。

### `actor`

- 含义：controller、processor、DPO、supervisory authority 等责任主体。
- ID：`ACTOR-{slug}`，例如 `ACTOR-DPO`。
- 路径：`wiki/actors/`。

### `contrast`

- 含义：考试中需要沿一个判断轴区分的相近规则、主体或期限。
- ID：`CONTRAST-{slug}`，例如 `CONTRAST-DPO-SA-POWERS`。
- 路径：`wiki/contrasts/`。

### `misconception`

- 含义：从真实作答理由中观察到的可跨题迁移旧模型。
- ID：`MC-{error-code}-{slug}`，例如 `MC-A-ADVICE-IS-APPROVAL`。
- 路径：`wiki/misconceptions/`。

### `question`

- 含义：教师侧题目导航页；不取代数据库中的完整题面和审计。
- ID：题库题为 `TQ-{三位题号}`，变式沿用既有 variant ID。
- 路径：`wiki/questions/`。

### `learning_event`

- 含义：一次真实作答、回收或修复事件；事件发生后不可改写，只能追加更正事件。
- ID：`LE-{YYYYMMDD}-{question-id}-{sequence}`。
- 路径：`wiki/learning-events/`。
- 展示：稳定 `id` 和文件名仅供后台处理；面向学习者必须提供可读 `title`／`display_title`，优先采用“Article／主题｜本次真正学会或纠正的区别”。事件索引及规则页反向链接必须显示该标题，不得直接显示 `CLAR-CHATGPT-*`、`VAR-*`、`REPAIR*` 等机器编号。

### `source`

- 含义：教材小节、官方法源或项目内原始记录的导航页。
- ID：教材为 `TEXTBOOK-{section}`；项目文件为 `FILE-{slug}`。
- 路径：`wiki/sources/`。

## 所有生成页的最小属性

```yaml
---
type: rule
id: RULE-GDPR-38-DPO-POSITION
title: Article 38 — Position of the DPO
generated: true
generated_on: 2026-09-11
source_refs:
  - 08-CIPPE结构化记忆笔记.md
authority_status: derived
review_status: current
---
```

要求：

- `id` 创建后保持稳定，不使用显示标题作为唯一身份。
- `generated: true` 明示页面可被重建。
- `source_refs` 至少包含一项真实来源；不得只写“AI 总结”。
- `authority_status` 只能反映来源状态，不得由链接数量推断。
- 学习掌握、题源真实性、法律核验是三个独立字段，不合并为一个“可信度”。

## 允许的关系

| 起点 | 关系 | 终点 | 示例 |
|---|---|---|---|
| question | `tests` | rule | `[[TQ 052]] → [[Article 38]]` |
| question | `revealed` | misconception | 题目暴露角色权限误读 |
| learning_event | `attempted` | question | 某日实际完成 TQ #52 |
| learning_event | `evidence_for` | misconception | 理由体现旧模型 |
| rule | `applies_to` | actor | Article 38 适用于 DPO 位置与组织支持 |
| contrast | `distinguishes` | rule/actor | DPO 与 SA 权限动词对比 |
| rule/question/event | `supported_by` | source | 指向教材小节或原始记录 |

双链表示导航关系，不自动证明法律支持、题目已核验或知识已经掌握。法律支持必须同时存在 `source_refs` 和相应状态字段。

## 首轮原型范围

- 主体：DPO、Supervisory Authority、Controller、Processor。
- 规则：GDPR Articles 37–39、78(2)、83(2)、83(4)–(6)。
- 题目：TQ #52、#72、#191。
- 错因：CIPP-027、CIPP-028、CIPP-029。
- 对比：建议/监督与批准；Article 12 一个月与 Article 78 三个月；罚款上限与具体裁量。

## 命名与语言

- 文件名优先使用稳定、短而明确的中英混合标题，禁止只用“笔记 001”一类序号。
- 页面正文以中文解释为主，保留决定法律范围的英文术语和题目触发词。
- 记忆比喻必须标记为 `memory_hook`，不得冒充正式法律分类。
- 教师侧问题页面必须标明可能泄露答案，不作为独立练习入口。
