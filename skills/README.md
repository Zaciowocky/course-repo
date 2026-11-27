# 技能目录

技能采用开放的 Agent-Skills 格式：一个目录一个技能，入口是 `SKILL.md`（YAML frontmatter + Markdown 正文）。
这样写出的技能可以被任何认识该格式的运行环境加载，不绑定本仓库。

| 技能 | 用途 | 负责人 |
|---|---|---|
| `course-material-generator/` | 由可信资料与课程规范生成一节课的 HTML 课件、实验与练习 | 邢家鑫 |
| （后续）`knowledge-extraction/` | 由原始资料产出知识点与来源登记 | 邢家鑫 |
| （后续）`exercise-generation/` | 由知识点产出练习、解析与易错点 | 谢文博 |

加载前置：`contracts/ids.yaml`、`contracts/knowledge.schema.json`、`contracts/manifest.schema.json`。
