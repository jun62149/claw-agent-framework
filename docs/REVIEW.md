# 源码审查与公开准备记录

审查日期：2026-11-17。结论基于本仓库源码与下述本地验证；未使用真实模型或 IM 凭据执行任务。

## 能力核实

| 审查项 | 已实现机制与源码 | 简历表述边界 |
| --- | --- | --- |
| Agent 执行循环 | `agent/loop.py`：最多 max_iterations 轮；带工具响应回填后继续；单轮多个工具依次 await | 可写多轮工具调度；不可写工具并行执行或自主规划算法 |
| Function Calling | `providers/openai_compat.py` 解析参数 JSON；`agent/tools/base.py` 提供定义；注册表执行；loop 用 tool_call_id 回填 | JSON 无效时降级为空字典，没有完整本地 Schema 校验 |
| MCP 接入 | `agent/tools/mcp.py`：stdio / ClientSession / initialize / list_tools / call_tool；复用 inputSchema；加服务名前缀 | 可写动态发现与统一适配；没有 HTTP/SSE 传输实现 |
| 执行限制与异常 | 注册表捕获工具异常；32 轮默认上限；30 条窗口内第 10 次警告、第 20 次熔断；Shell 60 秒超时、10000 字符截断 | 有防循环与错误回传，不能宣称完全可靠、沙箱或事务回滚 |
| 上下文 | `gateway.py` 按 channel:sender_id 缓存独立 AgentLoop；历史与重复调用窗口在实例内；context 拼装身份、时间、记忆 | 只隔离内存历史；同一用户跨群聊复用上下文，文件和长期记忆共享 |
| 持久化与压缩 | `session/manager.py` 有 JSONL API，但无主流程调用；`agent/memory.py` 有摘要生成和文件追加 | 不写断点恢复、持久会话或可靠长期记忆 |
| 多入口复用 | `channels/*` 将消息统一为 InboundMessage；MessageBus 双队列；Gateway 路由回复 | 四种入口实现存在；飞书和 QQ 仍需真实平台联调 |
| 异步职责 | Asyncio 负责队列、渠道、模型请求及 Shell；to_thread 处理输入/搜索/飞书发送；飞书线程回调安全投递 | Gateway 只有单个入站消费者，不能写多会话任务并行 |
| Web | FastAPI 提供页面，WebSocket 收发文本，UUID 标识每条连接 | 没有鉴权、持久登录会话或 token 流式输出 |
| 子 Agent / Skill | spawn 新建临时 Agent，默认最多两层、16 轮，await 返回；load_skill 读取文档 | 子 Agent 当前仍串行等待；技能是自然语言说明，不是 Python 插件执行器 |

## 需要后续处理的问题（本次未改核心逻辑）

1. `AgentLoop._save_to_history()` 在最终回答追加之前执行，因此最终 assistant 文本未进入历史；压缩后又按原历史长度切片，可能丢失新消息。
2. 压缩保留最后 6 条消息，可能打断 assistant/tool 配对。Token 是字符数粗估，实际触发阈值为两个配置值的较大者；max_tokens 没有传给 Provider。
3. MCP 双服务发现与调用可用，但 shutdown 非严格逆序退出上下文，已复现 AnyIO 取消作用域错误和 CancelledError。单个 poetry 服务测试可正常退出，不代表双服务生命周期正确。
4. 主入口快速 /exit 时，Web 服务可能出现 Uvicorn lifespan pending-task 警告；QQ stop 也未显式关闭 SDK，MCP 清理未由入口 try/finally 保证。
5. 文件路径校验使用 startswith，可被相同路径前缀绕过；Shell 正则黑名单不是安全沙箱。Web 默认绑定所有接口且无认证；只适合可信本地运行。
6. QQ 出站缺少原始消息类型和消息 ID，先尝试单聊再尝试群聊；真实平台效果待联调。Agent 缓存没有清退机制。

## 运行验证

环境：Windows、Python 3.12.7、独立 `.venv`；完整安装版本见 `requirements-lock.txt`。使用官方 PyPI 安装成功；本机默认镜像初次未解析到包。

| 检查 | 结果 |
| --- | --- |
| `python -X utf8 scripts/verify.py` | 7/7 通过：多轮及多工具回填、异常、迭代与重复限制、文件/Shell、会话路由、参数解析、页面/WebSocket |
| `python -m pip check` | 通过，未发现依赖冲突 |
| 公开 Python 文件 AST 解析 | 通过（最终文件集见 Git 索引） |
| `python -X utf8 scripts/verify_mcp.py` | 两个服务发现 6 个工具，poetry 调用成功；清理失败，退出码 1 |
| 主入口组装检查 | 模拟 /exit，使用测试密钥、临时目录、空 IM 凭据与无 MCP；可启动/退出，出现 lifespan 待清理任务警告 |
| 真实模型、搜索引擎、飞书及 QQ 联调 | 未执行；不消费用户密钥、不读取个人备忘录 |

Windows 默认 GBK 输出曾因 Emoji 日志报错，README 已采用 `-X utf8`；核心代码未为此改写。Git diff 空白检查发现原始源码 4 处行末空格，属于格式问题，本次保留。

## 公开文件与敏感信息

- 初始目录无 Git 元数据与远程配置，已新建 main 分支，避免覆盖已有仓库。
- `.gitignore` 排除 config.json、各类 .env、密钥文件、日志、缓存、虚拟环境、output 运行数据、data_project 员工数据及历史本地图文报告。文件保留在本地。
- output 仅放行两个已审查的示例技能目录。README 使用源码对应的 Mermaid 架构图，避免引用未经复核的历史图片。
- `scripts/audit_public.py` 扫描 Git 索引内容，匹配常见密钥格式、与本地配置的 5 个已填凭据字段比对，并拒绝运行数据及大于 5 MiB 文件；不输出凭据原文。
- 公开配置中的 sk-REPLACE_WITH_YOUR_DEEPSEEK_KEY 是占位符；飞书代码里的 a@b.com 是注释示例，无实际个人邮箱或硬编码真实密钥发现。扫描是规则检查，不能代替后续提交复核。
- GitHub 认证从本机 Git Credential Manager 获取，仅在内存中使用；不写入项目、URL 或日志。提交作者使用 GitHub noreply 地址。
- 新增/更新：README.md、.gitignore、requirements.txt、requirements-lock.txt、docs/RESUME.md、docs/REVIEW.md、scripts/verify.py、scripts/verify_mcp.py、scripts/audit_public.py。核心 Python 模块保持原实现。
