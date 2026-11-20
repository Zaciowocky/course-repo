# 契约目录

三人协作的接口层。所有跨模块的东西先在这里冻结，再写代码。

## 冻结规则

- 文件头必须有 `version` 字段；改动走 PR，三人会签（谢文博主评审）。
- **只增不改**：新增字段随时可以，修改或删除已有字段必须走 PR 并在群里通知。
- 各端启动时校验契约版本，不兼容就拒绝写入并提示。

## 目录

| 文件 | 内容 | 主导 | 状态 |
|---|---|---|---|
| `ids.yaml` | 七类 ID 的编码规则 | 谢文博 | v0.1 冻结 |
| `knowledge.schema.json` | `knowledge_points.yaml` 的字段 | 邢家鑫 | v0.1 冻结 |
| `manifest.schema.json` | 页面清单与挂点 | 邢家鑫 | v0.1 冻结 |
| `events.schema.json` | 学习事件 | 陈奕霖 | v0.1 冻结 |
| `mcp-tools.yaml` | MCP 工具与鉴权 | 谢文博 | v0.1 冻结（教师侧 2 个待定） |

后续补：`context.schema.json`（上下文包）、`overlay.schema.json`（补充格式）、`report.schema.json`（report.v0.2）、`migrations.schema.json`（迁移清单）。

## 未冻结项怎么处理

先在 Issue 里写清楚字段和用途，冻结后再写代码。**不要在各自代码里私自加字段。**
