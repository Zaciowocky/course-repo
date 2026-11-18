# 课程仓库（course-repo）

教学智能体的课程源仓库：课程规范、知识点与来源、生成产物、个性化扩展与工具链。

## 目录

| 路径 | 内容 | 谁写 |
|---|---|---|
| `course/syllabus.yaml` | 课程范围、课时、教学目标 | 教师／产品设计 |
| `course/knowledge/knowledge_points.yaml` | 知识点、先修、难度、评价标准 | 内容负责人 |
| `course/knowledge/sources.yaml` | 三层来源登记 | 内容负责人 |
| `course/knowledge/notes/` | 来源摘录与核验笔记 | 内容负责人 |
| `materials/` | 生成的 HTML 课件、实验、练习 | Codex（经 PR） |
| `overlay/` | 个性化补充（模板与样例，实际内容在学生本地） | 学伴 |
| `tools/` | 校验与制作脚本 | 平台负责人 |
| `docs/` | 数据契约、协作流程、变更说明 | 全体 |

## 快速开始

```bash
git clone <repo>
cd course-repo
python tools/check_course.py     # 本地跑一遍校验
```

## 协作

- 任务都在 Issue 里，没有验收标准不开工。
- 一人一分支，`feat/<issue>-<描述>` 或 `fix/<issue>-<描述>`，PR 汇入 `main`。
- `main` 受保护：必须 PR、至少一人 review、CI 通过。
- 详细约定见 `docs/workflow.md`，数据字段见 `docs/contract.md`。

## 发布

审核通过的课程打 tag（`v0.1.0`、`v0.1.1`……），学生端只拉取已发布 tag。
每次发布在 `CHANGELOG.md` 里记录变更、受影响知识点与迁移说明。
