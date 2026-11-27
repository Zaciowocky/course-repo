# 课程 MCP 服务（mock 版）

阶段①—③期间给 A、B 联调用的假服务：接口形状与契约一致，数据存在内存里，重启即清空。

## 跑起来

```bash
cd services/course-mcp
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
# 打开 http://127.0.0.1:8000/docs 看所有接口
```

## 鉴权

学生端：先注册换 token，之后每次请求带 `Authorization: Bearer <token>`。

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"student_id": "2026101", "invite_code": "INV-ALPHA"}'
```

教师端：用教师邀请码注册，`role` 为 `teacher`，才能调 `get_class_view` 与 `list_issues`。

## 已实现的工具

| 工具 | 方法 | 谁可调用 |
|---|---|---|
| `auth/register` | POST | 所有人（学号 + 一次性邀请码） |
| `tools/get_course_version` | GET | 学生、教师 |
| `tools/report_progress` | POST | 学生 |
| `tools/get_announcements` | GET | 学生、教师 |
| `tools/report_issue` | POST | 学生 |
| `tools/get_class_view` | GET | 仅教师 |
| `tools/list_issues` | GET | 仅教师 |

教师侧还剩两个工具（任务书里写的是 4 个），等周报需求定了再补。

## 现在的假数据

- 课程 `RAG`，最新 tag `v0.1.0`
- 两个学生邀请码：`INV-ALPHA`、`INV-BETA`；一个教师邀请码：`INV-TEACHER`
- 班级视图里上报人数少于 5 的知识点，返回 `suppressed: true` 且不给数字

## 与契约的关系

字段以 `contracts/mcp-tools.yaml` 为准。`report_progress` 的完整校验要等
`contracts/report.schema.json`（report.v0.2）冻结后接入，现在只做基础字段检查。
