# 协作流程

## Issue

- 所有任务先开 Issue，模板四项：背景、验收标准、涉及契约、依赖。
- 标签：`type/feat`、`type/fix`、`area/teacher`、`area/student`、`area/infra`、`blocked`。
- 看板：Todo / Doing / Review / Done；每人同时在 Doing 的不超过两个。

## 分支与 worktree

- 分支命名：`feat/<issue号>-<短描述>`、`fix/<issue号>-<短描述>`。
- 一个 Issue 一个 worktree，放在仓库外的 `.worktrees/<issue号>`：

  ```bash
  git worktree add ../.worktrees/12 feat/12-make-session
  ```

- 新功能与 bug 并行：功能在 `feat/*` 的 worktree 里写，bug 从 main 拉 `fix/*` 的 worktree 单独修，互不打断。
- 合并后清理：`git worktree remove ../.worktrees/12`。

## PR

- 只做一件事，改动超过 400 行就拆。
- 必须：CI 通过、至少一人 review、关联 Issue。
- 描述三行：改了什么、怎么验证、关联哪个 Issue。
- 合并方式 squash，提交信息带 Issue 号。

## 节奏

- 周一：Issue 规划与认领；
- 周三：联调窗口，只在这天改接口；
- 周五：各写 200 字进展，更新看板。
