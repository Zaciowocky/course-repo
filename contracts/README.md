# 契约目录

三人协作的接口层。所有跨模块的东西先在这里冻结，再写代码。

## 冻结规则

- 文件头必须有 `version` 字段；改动走 PR，三人会签（邢家鑫主评审）。
- **只增不改**：新增字段随时可以，修改或删除已有字段必须走 PR 并在群里通知。
- **新增枚举值时，消费者遇到未识别的值必须忽略并计数，不得抛错**（例如 `op` 新增了 `ask` / `revisit` / `answer_change`）。
- 各端启动时校验契约版本，不兼容就拒绝写入并提示。

## 目录

| 文件 | 内容 | 主导 | 状态 |
|---|---|---|---|
| `ids.yaml` | 七类 ID 的编码规则 | 谢文博 | v0.1 冻结 |
| `knowledge.schema.json` | `knowledge_points.yaml` 的字段 | 邢家鑫 | v0.1 冻结 |
| `manifest.schema.json` | 页面清单与挂点 | 邢家鑫 | v0.1 冻结 |
| `events.schema.json` | 学习事件 | 陈奕霖 | v0.2 冻结 |
| `context.schema.json` | 上下文包（工作台 → 学伴） | 陈奕霖 | v0.1 冻结 |
| `mcp-tools.yaml` | MCP 工具与鉴权 | 谢文博 | v0.1 冻结（教师侧 2 个待定） |

后续补：`overlay.schema.json`（补充格式）、`report.schema.json`（report.v0.2）、`migrations.schema.json`（迁移清单）。

## 变更记录

### events v0.2（只增不改，v0.1 事件照样合法）

| 新增 | 用途（任务书） |
|---|---|
| `event_id`（UUID） | 证据表“来源事件 ID 列表”（4.3） |
| `ts`（ISO 8601 带时区） | pyBKT 作答顺序、遗忘模型、错题“首次出错时间”（4.2、4.3）；不上报 |
| `session_id`（S01） | 课节画像；warm-up、复习等无页面事件的归属（4.3） |
| `item_kind`（check / homework / diagnostic / followup / review） | 证据表“证据类型”（4.3） |
| `is_transfer` | “可迁移”档判定（4.3） |
| `item_hash` | 学伴出题的题目 ID（4.2 错题本） |
| `misconception`（MIS 编码或 other，仅限做错的作答） | 误区列表与上报误区计数（4.3、4.4） |
| `op` 增加 `ask` / `revisit` / `answer_change` | 纠结信号：提问、回跳、改答（4.3） |

其他变化：

- `duration_s` 上限 600 → 3600（只放宽，v0.1 事件仍合法）：本地事件保留真实时长，上报口径由 `report.schema.json` 规定。
- 新增的 op 带约束：`revisit` 必须带 `page_id`，`answer_change` 必须带 `activity_id` 或 `item_hash`。`op=answer` 为兼容 v0.1 不强制题目标识。
- `event_id`、`ts` 在 schema 中可选（兼容 v0.1），写入 learner.db 事件表时由写入方补齐。
- 消费者遇到未识别的 op 必须忽略并计数，见上方冻结规则。
- 给旧字段补了中文 `description`（含 `hint_level` 0—4 各级含义），含义不变。

### context v0.1

学生提问或求提示时工作台附带的学习位置：课程版本、课节、知识点、页面、节点、触发方式、提示层级、当前活动、最近 5 次作答。请求体约定为 `{"message": 学生原话, "context": 上下文包}`，上下文包本身不含自由文本，可原样附在 `report_issue` 的 `context` 里。

## 未冻结项怎么处理

先在 Issue 里写清楚字段和用途，冻结后再写代码。**不要在各自代码里私自加字段。**
