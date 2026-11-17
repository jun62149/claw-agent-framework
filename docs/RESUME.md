【项目名称】CLAW智能Agent框架

【技术栈】Python、Asyncio、OpenAI SDK、Function Calling、MCP、FastAPI、WebSocket

【项目描述】
支持通过命令行、网页及配置后的飞书、QQ机器人使用智能助手，完成文件读写、命令执行与联网检索。
可连续调用工具处理多步骤任务，并通过MCP服务扩展备忘录、诗词查询等能力。

【技术亮点】
- 自主实现Agent执行循环，串联模型决策、工具调度与结果回填，支持多轮调用、迭代上限及重复调用熔断。
- 封装Function Calling工具注册与参数解析，通过MCP stdio动态发现工具、映射Schema并统一调度。
- 基于Asyncio消息总线统一接入CLI、Web及IM渠道，按渠道与用户维护独立Agent实例及内存对话历史。
