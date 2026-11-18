# 数据契约 v0.1（草稿）

本文件是所有模块共用的字段与接口约定。**只增不改**，改字段要走 PR 并通知全组。

## 1. 标识规则

| 对象 | 格式 | 示例 |
|---|---|---|
| 课程 | `^[A-Z]+-\d{3}$` | `RAG-101` |
| 知识点 | `KP-<课程前缀>-<两位序号>` | `KP-RAG-01` |
| 页面 | `PG-<节号>-<两位序号>` | `PG-S01-01` |
| 题目 | `EX-<知识点序号>-<两位序号>` | `EX-01-01` |
| 来源 | `SRC-<两位序号>` | `SRC-01` |
| 个性化扩展 | `OV-<知识点序号>-<两位序号>` | `OV-01-01` |

## 2. 学习事件字段

| 字段 | 类型 | 说明 |
|---|---|---|
| course_id | string | 课程 ID |
| version | string | 课程版本号 |
| kp_id | string | 知识点 ID |
| page_id | string | 页面 ID |
| activity_id | string | 活动 ID，可为空 |
| op | enum | page_enter／page_leave／interact／answer／hint |
| result | enum | correct／incorrect／partial／none |
| hint_level | int | 0—4，未用提示为 0 |
| duration_s | int | 该事件用时秒数，>600 记为 600 |
| done | bool | 是否完成该活动 |

**不上报**：对话原文、自由文本作答、精确时间戳、设备信息。

## 3. MCP 五类动作

| 动作 | 入参 | 返回 |
|---|---|---|
| 课程查询 | course_id, version? | 版本清单、知识点列表 |
| 证据上报 | 事件数组（见第 2 节） | 接收条数、失败条数 |
| 版本与公告 | course_id | 最新 tag、公告列表 |
| 教师支持请求 | course_id, kp_id, 问题描述 | 请求 ID、预计回复时间 |
| 班级汇总读取 | course_id, kp_ids[] | 知识点级统计与样本量 |

所有调用需携带身份令牌；服务端按作用域校验，越权返回 403。

## 4. 个性化扩展绑定

| 字段 | 说明 |
|---|---|
| course_version | 生成时的课程版本 |
| kp_id / kp_rev | 知识点及其修订号 |
| page_id | 挂载页面 |
| node_id | 页面内的扩展节点 |
| evidence | 触发证据（事件摘要） |

返回状态：`page_id`、`task_id`、`progress`、`return_to`。

## 5. 变更流程

1. 在 Issue 里写清字段与影响范围；
2. 提 PR 修改本文件与对应 schema；
3. 至少一人 review，涉及他人模块需对方同意；
4. 合并后在群里发一条变更通知。
