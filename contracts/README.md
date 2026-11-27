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
| `report.schema.json` | 进度上报 report.v0.2 | 邢家鑫 | v0.2 冻结 |
| `state-gate.yaml` | 四档状态到教学动作与补充种类的门控（本地 MCP 工具任何状态都可调用） | 陈奕霖 | v0.1 冻结 |
| `learner.sql` | 学生本机 learner.db 建表语句：画像 5 表 + 误区子表、记忆 4 库、只追加的事件表 | 陈奕霖 | v0.1 待会签（C） |
| `profile-rules.yaml` | 画像判定规则：有效证据、BKT、四档阈值、待确认、误区消退、遗忘、错题五盒 | 陈奕霖 | v0.1 待会签（C） |

后续补：`overlay.schema.json`（补充格式）、`migrations.schema.json`（迁移清单）、`local-mcp-tools.yaml`（本地 MCP 14 个工具的请求与响应，契约⑭的工具清单部分）。

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

### report v0.2

学伴每节课结束向课程 MCP 服务上报一次，服务端按 `report_id` 去重、按学生+版本+课节+知识点合并。

| 字段组 | 内容要点 |
|---|---|
| 基本信息 | schema 版本、报告 ID、课程与版本、课节、统计时段（精确到日）、上报档位、契约与工作台版本 |
| 课节进度 | 页面总数与完成数、warm-up 分流去向、学习时长 |
| 每知识点统计 | 四档状态、掌握概率区间、作答与独立/提示后/做错次数、最高提示级别、迁移题、误区编码计数、提问与未解决数、复习到期与完成数、用时 |
| 内容缺口 | 页面 ID、知识点 ID、找不到答案的提问次数 |
| 补充统计 | 生成的补充数、降级为提示的次数 |

两条硬约束：

- **不上报**：聊天原文、问题原文、题干与答案原文、错题本条目、讲解偏好、自述基础、误区证据、遗忘参数、精确掌握概率、逐条事件与精确时间戳。结构上由 `additionalProperties: false` 挡住，多一个字段就校验失败。
- **用时按每次停留钳到 600 再累加**：本地事件保留真实时长（events v0.2 上限 3600）；上报时每次页面停留超过 600 记 600，`kp_stats[].duration_s` 是截断后的累计值，上限一天（与 `study_seconds` 一致）。

`tier: "minimal"` 时只保留进度与 `kp_id` + `state`，其余统计字段一律不出现。

### learner.db v0.1 与 profile-rules v0.1（契约⑭）

学生本机的画像与学伴记忆库，由本地 MCP server 独占读写（任务书 4.2、4.3）。

| 表 | 任务书名称 | 要点 |
|---|---|---|
| `events` | 事件表 | 列与 events.schema.json v0.2 一一对应；触发器禁止改、删 |
| `student_profile` | 基础画像 | 只有一行；`report_tier` 为空表示还没授权上报 |
| `kp_state` | 课程画像 | 每知识点一行；计数字段与 report 的 `kp_stats` 同名，上报直接取 |
| `kp_misconceptions` | 课程画像的误区列表 | 拆成子表，方便判断“有没有仍在出现的误区” |
| `lesson_state` | 课节画像 | 当前位置、补习返回栈、活动状态、用过的补充 |
| `evidence` | 证据表 | 每次状态变化一行，`event_ids` 指回具体事件 |
| `corrections` | 更正记录 | 学生说“我其实会了 / 没懂”，验证题结果决定是否采纳 |
| `mistakes` / `qa_memory` / `strategies` / `sessions` | 记忆四库 | 学生可逐条删除；原文列标 [仅本地] |

几条约定（详见两份文件的注释）：

- **事件表的枚举不写 CHECK**：SQLite 改 CHECK 要重建表，只追加的表不能重建。op、item_kind 等新增取值由本地 MCP server 按契约校验后照常写入。
- **提示后做对在 BKT 里记“错”**：只有独立做对（`hint_level = 0`）记“对”；提示后做对另计 `correct_with_hint`。
- **待确认不是第五档**：`pending = 1` 时掌握概率照常更新，`state` 保持最近一次确认的档位，从没确认过就是 `unseen`；上报的也是这个档位。
- **BKT 参数用课程级的**：学生本机只有一个人的数据，拟合不出参数；先按知识点难度取初值，试测时用 pyBKT 离线拟合后回写。
- **保持率只排复习提醒**：遗忘模型不改掌握概率和四档。
- **清空全部数据 = 删除 learner.db 文件**：事件表不能逐条删，记忆四库可以。

## 未冻结项怎么处理

先在 Issue 里写清楚字段和用途，冻结后再写代码。**不要在各自代码里私自加字段。**
