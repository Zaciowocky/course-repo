# Hermes 进程内调用验证结论（第 10 周）

> 负责：陈奕霖（成员 B）　日期：2026-11-27
> 对应任务书：2.2 第 10 周交付物；4.5「工作台 ↔ 学伴：本地 HTTP + JSON，SSE 流式回答；后端进程内调用 Hermes AIAgent，不顺则改为转发常驻 Hermes 进程，接口不变」。

## 结论

**进程内调用可行，采用。**工作台后端（FastAPI）在自己进程里为每个请求新建一个 `AIAgent`，用 `stream_delta_callback` 接住逐字输出，经 SSE 推给浏览器。9 项检查全部通过，备选的"常驻 Hermes 进程"无需启用。

前提是照做下文「必须的配置」里的 9 条；其中两条（日志、系统提示）关系到隐私，不做会把学生原话写进本地日志、把电脑用户名发给模型服务商。

尚未用真实模型实测首字延迟（组里还没定模型和 API key），见「尚未验证」。

## 环境

| 项 | 值 |
|---|---|
| Hermes | v0.23.4（2026-11-23 正式版），源码安装，可编辑模式 |
| Python | 3.14（Hermes 的 46 个核心依赖只在 3.14 下安装，3.11 的 `course` 环境装不了） |
| 系统 | Windows 11 原生（未用 WSL） |
| 安装方式 | pip 解不开 `browser-harness` 与 Pillow 的版本冲突；用 `uv export --frozen --extra mcp` 导出官方锁文件，再 `uv pip install --no-deps --require-hashes` 逐包校验安装，结果与官方安装器一致 |

## 怎么测的

不需要 API key：本机起一个 OpenAI 兼容的**假模型服务**，每 20 ms 吐一个字，并把收到的每个请求（工具列表、系统提示）记下来作为证据。工作台是一个最小 FastAPI 后端：校验上下文包 → 后台线程里建 `AIAgent` → 回调片段进 asyncio 队列 → SSE 推出。测试脚本自动起停两个服务，跑完打印结果。

验证代码暂存在本地 `D:\kykt\student-spikes\hermes-inproc\`（学生端代码位置定下来后移入）：

| 文件 | 作用 |
|---|---|
| `fake_llm.py` | 假模型服务 |
| `workbench.py` | 最小工作台后端（含下文全部配置） |
| `run_checks.py` | 自动跑 C0—C8；换真模型只需设 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` 后重跑 |
| `profile_cold.py` | 冷启动剖析 |

## 结果（2026-11-27，假模型）

| # | 检查 | 结果 | 数据 |
|---|---|---|---|
| C0 | 模型基准（不经 Hermes） | — | 首字 0.075 s |
| C1 | 进程内调用 + SSE 逐字 | ✅ | 52 个片段逐字到达；首字 0.162 s，**比直接问模型多 0.087 s**；建 Agent 0.1 s |
| C2 | 3 人同时提问 | ✅ | 各自完整、无串台；总耗时 1.78 s（单人 1.73 s，排队需约 5.2 s），3 个线程并行 |
| C3 | 不合格上下文包被拒 | ✅ | 夹带原话 / 知识点 ID 错 / 缺 `trigger` 均返回 422 |
| C4 | 工具与系统提示 | ✅ | 发给模型的工具 0 个；系统提示含知识点 ID；人设为学伴 |
| C5 | 不另存原话、不写长期记忆 | ✅ | Hermes 数据目录 8 个文件，无一含学生原话；`memories/` 为空 |
| C6 | 学生关页面后停止生成 | ✅ | 模型端在第 4/52 字时断开 |
| C7 | 启动与预热 | ✅ | 进程启动到可服务约 5 s（其中预热 2.9 s） |
| C8 | 系统提示无本机隐私 | ✅ | 806 字，不含用户名、用户目录、工作目录、数据目录路径 |

## 必须的配置（第 11 周工作台照此实现）

| # | 配置 | 不做的后果（实测） |
|---|---|---|
| 1 | `enabled_toolsets=[]`（白名单） | 默认给模型 18 个工具，含 `terminal`、`write_file`、`execute_code`；按文档用黑名单关掉 terminal / browser / file / web 后**仍剩 10 个**，`execute_code`、`delegate_task` 照样在。违反「原始课件只读」 |
| 2 | 每个请求新建 `AIAgent`，放后台线程跑 | 官方说明不是线程安全；热态建一个只要 0.03—0.1 s |
| 3 | `stream_delta_callback` + `loop.call_soon_threadsafe` 进队列 → SSE | 回调只收到非空文字，模型的 `<think>` 思考内容已被 Hermes 过滤 |
| 4 | 启动时预热：对工作台自带的本机假接口空跑一次 | 冷启动首字约 6—8 s（加载上千个模块，非联网）；预热后首字只比模型多约 0.05—0.09 s。预热不调用真实模型，不花 token |
| 5 | `HERMES_HOME` 指向工作台自己的数据目录 | 默认在 AppData；从桌面应用等环境启动时 AppData 写入会被重定向。也避免读写学生本机的全局 Hermes 配置 |
| 6 | `HERMES_HOME/config.yaml` 写 `logging: {level: WARNING}` | 默认 INFO 会把每条提问原文写进 `logs/agent.log`，学生在「我的记录」里删除记录时删不到这份 |
| 7 | 屏蔽系统提示里的本机信息（工作台里 3 处补丁，见 `workbench.py`） | 默认附加用户名、用户目录、工作目录、操作系统、Python 版本、数据目录路径，**随每次请求发给模型服务商**，且没有配置开关。屏蔽后系统提示由 3702 字降到 806 字，也省钱 |
| 8 | `HERMES_HOME/SOUL.md` 写学伴人设，并传 `load_soul_identity=True` | 默认人设是 "You are Hermes Agent"；`skip_context_files=True` 时不传此参数就不读 SOUL.md |
| 9 | `skip_memory=True`、`skip_context_files=True`，不传 `session_db` | 学伴记忆统一在 learner.db（任务书 4.2）；不读工作目录里的 AGENTS.md 等文件 |

另外两条约束：

- **模型的上下文窗口必须 ≥ 64K token**，否则 Hermes 启动时直接报错拒绝运行（实测）。主流云端模型一般为 128K；若考虑学生本机跑小模型，须先确认这一条。
- 学生中途关页面时调用 `agent.interrupt(hard_cancel=True)`，否则模型会在后台继续生成、继续计费。

## 尚未验证

| 项 | 计划 |
|---|---|
| 真实模型的首字延迟与费用 | 组里定模型和 API key 后，设 3 个环境变量重跑 `run_checks.py` 补数 |
| 本地 MCP server 接入后的工具白名单 | 第 12 周（任务书 4.5「画像与记忆接入」）：白名单改为只含本地 MCP 工具集，补一项检查 |
| 系统提示里剩余的 Hermes 文档提示（约 400 字，无隐私） | 可再屏蔽，优先级低 |
| 常驻 Hermes 进程（API Server）备选 | 主方案已通过，暂不实测 |
| Hermes 升级 | 补丁依赖内部函数名；每次升级后重跑 `run_checks.py`，C4、C8 会发现补丁失效 |

## 附：工作台调用核心代码

```python
agent = AIAgent(
    base_url=LLM_BASE_URL, api_key=LLM_API_KEY, model=LLM_MODEL,
    quiet_mode=True,
    enabled_toolsets=[],          # 白名单为空：0 个工具
    skip_memory=True,             # 学伴记忆走 learner.db
    skip_context_files=True,      # 不读工作目录里的 AGENTS.md
    load_soul_identity=True,      # 但读 HERMES_HOME/SOUL.md（学伴人设）
    max_iterations=4,
    ephemeral_system_prompt=build_system_prompt(context),   # 上下文包 → 中文背景设定
    stream_delta_callback=lambda text: loop.call_soon_threadsafe(queue.put_nowait, text),
)
result = agent.run_conversation(user_message=message)       # 在后台线程里调用
```
