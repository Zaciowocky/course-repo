# 课程 MCP 服务（mock 版）

阶段①—③给教师端和学生端联调用的假服务：**接口与校验按契约执行**，数据存在内存里，重启即清空。

## 跑起来

```bash
cd services/course-mcp
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
# http://127.0.0.1:8000/docs
```

## 校验以契约为准

`report_progress` 的报文直接按 `contracts/report.schema.json` 校验，服务端不重复定义字段：

- 少必填字段 → 422 `DATA-422-01`，并指出字段路径（如 `period`、`kp_stats.0.state`）
- 多一个字段（比如 `question_text`）→ 同样 422，隐私红线由结构挡住
- `schema_version` 不是 `report.v0.2` → 422
- `course_version` 不是当前 tag → 200，但 `accepted: 0`、`DATA-422-03`

客户端可以从 `get_course_version` 的 `report_schema_version` 拿到应使用的上报格式。

## 鉴权

学生端先注册换 token，之后每次请求带 `Authorization: Bearer <token>`：

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"student_id":"2026101","invite_code":"INV-ALPHA"}'
```

- 邀请码一次性使用，用后即失效
- token 默认 7 天过期（`AUTH-401-02`），可主动吊销（`POST /auth/revoke`，再访问返回 `AUTH-401-03`）
- 角色不符 → 403 `AUTH-403-01`

## 接口

| 接口 | 谁可调用 | 说明 |
|---|---|---|
| `POST /auth/register` | 所有人 | 学号 + 一次性邀请码换 token |
| `POST /auth/revoke` | 已登录 | 吊销自己的 token |
| `GET /tools/get_course_version` | 学生、教师 | 返回 tag、变更说明与上报格式版本 |
| `POST /tools/report_progress` | 仅学生 | 按 report.v0.2 校验、report_id 去重、版本闸 |
| `GET /tools/get_announcements` | 学生、教师 | 公告 |
| `POST /tools/report_issue` | 仅学生 | 学生主动求助，教师可在 list_issues 看到 |
| `GET /tools/get_class_view` | 仅教师 | 班级视图，含四类标记与小样本抑制 |
| `GET /tools/list_issues` | 仅教师 | 待处理的学生问题 |
| `GET /healthz` | 公开 | 探活 |

## 班级视图的口径

- 每名学生、每个知识点只取 **`period.to` 最大、同日期取后到的一条**
- 上报人数 < 5 的知识点返回 `suppressed: true`，不给任何数字
- 四类标记（阈值见 `app.py` 顶部常量，可改）：

| 标记 | 条件 |
|---|---|
| `unmastered_high` | 未掌握（unseen + gap）比例 ≥ 0.6 |
| `hint_dependent` | 提示后正确率 − 独立正确率 ≥ 0.25 |
| `misconception_common` | 同一误区编码出现在 ≥ 30% 的学生身上 |
| —— | 同一页面被 ≥ 3 名学生报内容缺口时，列在 `content_gaps` |

## 假数据

- 课程 `RAG`，最新 tag `v0.1.0`
- 学生邀请码 `INV-ALPHA` / `INV-BETA`，教师邀请码 `INV-TEACHER`
- 数据只在内存，重启清空

## 换成 PostgreSQL

表结构与迁移步骤见 `docs/`（待补）。现有代码把 `TOKENS`、`REPORTS`、`ISSUES` 三个字典换成仓储层即可，
接口与校验逻辑不用动。注意两点：

- 保留 `report_id` 主键，靠唯一约束去重，不要先查后插
- 「每名学生最新一条」用窗口函数或 `DISTINCT ON`，不要用循环
