# 制作任务单（模板）

> 一次课件生产任务 = 一张任务单 + 一个 worktree + 一条任务分支 + 一个 PR。
> 修订轮次在任务单号后加 `-revN`（如 `TASK-2026-001-rev2`），提交信息以 `revN:` 开头。

```yaml
task_id: TASK-<年份>-<序号>        # 如 TASK-2026-001；修订追加 -revN
base_version: v<x.y.z>             # 从哪个已发布 tag 开分支；首版填 none
branch: task/<task_id>             # 教师 Agent 令牌只允许推 task/*
scope:
  sessions: [S01]                  # 本次涉及的课节
  knowledge_points: [KP-RAG-001]   # 必须全部覆盖；缺来源的 KP 直接报错停工
  allow_write:                     # 允许改动的目录（之外的一律不碰）
    - materials/S01/
    - materials/manifest.yaml
  frozen: []                       # 明确不许改动的页面或文件
brief: |                           # 教师意图原文（OpenClaw 会话或 PR 留言）
  （老师的需求 / 审阅意见原文粘贴于此）
requirements:
  coverage: 必修知识点覆盖率 100%
  checks:                          # 提交前必须全过
    - python tools/build_manifest.py
    - python tools/check_course.py
    - python -m pytest -q
reviewer: <教师账号>               # 合并与打 tag 仅教师本人
```

## 填写规则

1. `knowledge_points` 只从 `course/knowledge/knowledge_points.yaml` 里选，不新造 ID。
2. `allow_write` 之外的路径出现改动，PR 一律打回。
3. 修订（rev-N）时只改 `brief` 涉及的页面，`scope` 其余部分保持不变。
4. 任务失败：删除 worktree 与分支，主分支不受影响；推倒重来另开新任务单并链接旧 PR。
