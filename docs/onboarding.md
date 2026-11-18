# 新成员上手指南

> 面向第一次参与这个仓库的人。全程 Windows，命令直接复制。

## 一、你要做的事

仓库里所有工作都从 Issue 开始。先去 [Issues](../../issues) 看你负责的那条，读背景和验收标准，然后按本文走一遍流程。

| 谁 | 负责 | 第一条 Issue |
|---|---|---|
| 邢家鑫 | 课程生产（块 1） | #1 |
| 陈奕霖 | 学生学习（块 2） | #2 |
| 谢文博 | 班级闭环（块 3）＋数据契约 | #4（先做这个），再做 #3 |

## 二、第一次配置（只做一次）

### 1. 装 Git 并确认版本

```bash
git --version
```

没有的话装 [Git for Windows](https://git-scm.com/download/win)，装完重开终端。

### 2. 配名字和三项必须的设置

```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
git config --global core.autocrlf false
git config --global core.longpaths true
git config --global core.quotepath false
```

后三项不配的话，Windows 上会出现"改了一行却显示整篇变更""中文文件名乱码"这类问题。

### 3. 配 SSH（推荐）

```bash
ssh-keygen -t ed25519 -C "你的邮箱"
```

一路回车（密码可以留空）。然后把公钥贴到 GitHub：

```bash
cat ~/.ssh/id_ed25519.pub
```

复制输出，打开 https://github.com/settings/keys → **New SSH key** → 粘贴 → 保存。

验证：

```bash
ssh -T git@github.com
```

看到 `Hi <你的用户名>!` 就成了。看到 `Permission denied` 说明公钥没贴对。

> 不想配 SSH 也可以走 HTTPS：clone 时用 `https://github.com/Zaciowocky/course-repo.git`，第一次推送会弹浏览器登录，登录一次之后会记住。

### 4. 克隆并跑通校验

```bash
cd D:\kykt
git clone git@github.com:Zaciowocky/course-repo.git
cd course-repo
pip install pyyaml
python tools/check_course.py
```

看到「校验通过」就说明环境没问题。

## 三、做一件活的完整流程

以 Issue #2 为例（把 2 换成你的 Issue 号，`student-flow` 换成简短描述）：

```bash
# 1. 更新主干并建 worktree（目录在仓库外）
cd D:\kykt\course-repo
git fetch
git worktree add -b feat/2-student-flow D:\kykt\.worktrees\2 origin/main

# 2. 在 worktree 里干活
cd D:\kykt\.worktrees\2
# ……改代码、写内容……

# 3. 本地自检
python tools/check_course.py

# 4. 提交并推送
git add -A
git commit -m "feat: 学生端 warm-up 三分流 (#2)"
git push -u origin feat/2-student-flow

# 5. 去 GitHub 开 PR
#    push 完终端会打印一个链接，点开即可；记得在描述里写 Closes #2
```

PR 开出来后找另外两个人中的一个人 review，通过后由你自己点 **Squash and merge**。

合并后清理：

```bash
cd D:\kykt\course-repo
git worktree remove D:\kykt\.worktrees\2
git branch -d feat/2-student-flow
git pull
```

## 四、三条铁律

1. **不直接推 main。** main 受保护，推了也会被拒；所有改动走分支 + PR。
2. **没有验收标准不开工。** Issue 里没写清楚"做完算什么"，先在 Issue 里问，别猜。
3. **PR 只做一件事，超过 400 行就拆。** 400 行以上的 PR 没人能认真看完。

## 五、报错对照表

| 报错 | 原因 | 怎么办 |
|---|---|---|
| `Repository not found` | 还没被加进协作者，或 SSH 没配 | 找邢家鑫邀请你，再测 `ssh -T git@github.com` |
| `Permission denied (publickey)` | 公钥没加到 GitHub | 重做第二节第 3 步 |
| `already checked out at ...` | 这个分支已经在另一个 worktree 里 | 换个分支名，或先 `git worktree list` 看看 |
| `protected branch` / 推 main 被拒 | 开了分支保护 | 建分支推，走 PR |
| `Updates were rejected` | 远端有你没有的提交 | `git pull --rebase origin main` 再推 |
| 改一行显示整篇变更 | 换行符问题 | 确认 `core.autocrlf false`，等 `.gitattributes` 合进来 |
| 中文文件名显示成 `\344\275...` | 编码显示问题 | `git config --global core.quotepath false` |
| `check_course.py` 报"缺少 pyyaml" | 没装依赖 | `pip install pyyaml` |

## 六、节奏

- **周一**：看一下看板，认领本周要做的 Issue，`Doing` 里最多两个。
- **周三**：联调窗口。涉及字段或接口的改动只在这天合。
- **周五**：在对应 Issue 下写三行——做了什么、卡在哪、下周做什么。

## 七、有问题问谁

| 问题类型 | 找谁 |
|---|---|
| 仓库、分支、CI、权限 | 邢家鑫 |
| 字段定义、接口、任务拆得对不对 | 谢文博 |
| 学生端体验、课件该长什么样 | 陈奕霖 |
