import asyncio
import os
import sys

from config import load_config
from providers.openai_compat import OpenAICompatProvider
from agent.tools.registry import ToolRegistry
from agent.tools.filesystem import ReadFileTool, WriteFileTool, ListDirTool
from agent.context import ContextBuilder
from agent.loop import AgentLoop
from agent.tools.shell import ExecTool
from agent.tools.web_fetch import WebFetchTool
from agent.tools.web_search import WebSearchTool
from agent.tools.system_info import SystemInfoTool
from agent.tools.skill_loader import LoadSkillTool
from agent.tools.spawn import SpawnSubagentTool
from agent.tools.mcp import MCPClientManager
from agent.memory import MemoryConsolidator
from bus.queue import MessageBus
from channels.cli import CLIChannel
from gateway import Gateway
from channels.qq import QQChannel
from channels.feishu import FeishuChannel
from channels.web import WebChannel

def build_agent(config, session_key: str, mcp_tools: list | None = None) -> AgentLoop:
    """构建 Agent 实例

    Args:
        config: 配置对象（由 load_config() 返回）
        session_key: 会话标识，格式为 "{channel}:{sender_id}"
        mcp_tools: MCPClientManager 已发现的 MCP 工具列表（可选）
    """
    if not config.api_key:
        print("错误：未配置 API_KEY，请在 config.json 中设置或设置环境变量 NANOCLAW_API_KEY")
        sys.exit(1)

    # 创建 LLM Provider
    provider = OpenAICompatProvider(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model
    )

    # 创建工具注册中心
    tools = ToolRegistry()
    tools.register(WebFetchTool())
    tools.register(WebSearchTool())
    tools.register(ExecTool(config.workspace))
    tools.register(ReadFileTool(config.workspace))
    tools.register(WriteFileTool(config.workspace))
    tools.register(ListDirTool(config.workspace))
    tools.register(SystemInfoTool())
    tools.register(LoadSkillTool(os.path.join(config.workspace, "skills")))

    # 注册子 Agent 工具（provider_factory 按 model 新建 Provider）
    def provider_factory(model: str | None) -> OpenAICompatProvider:
        return OpenAICompatProvider(
            api_key=config.api_key,
            base_url=config.base_url,
            model=model or config.model
        )
    tools.register(SpawnSubagentTool(
        provider_factory=provider_factory,
        tools_registry=tools,
        workspace=config.workspace,
    ))

    # 注册 MCP 工具（若已连接 MCP 服务器）
    if mcp_tools:
        for tool in mcp_tools:
            tools.register(tool)


    # 创建上下文构建器
    context = ContextBuilder(
        workspace=config.workspace,
        identity_file=config.identity_file
    )

    # 创建记忆压缩器实例
    consolidator = MemoryConsolidator(
        provider=provider,
        workspace=config.workspace,
        token_budget=config.token_budget,
        max_tokens=config.max_tokens,
        consolidation_threshold=config.consolidation_threshold
    )

    # 创建 Agent 循环
    agent = AgentLoop(
        provider=provider,
        tools=tools,
        context=context,
        model=config.model,
        session_key=session_key,
        max_iterations=config.max_iterations,
        consolidator=consolidator
    )

    print(f"已注册工具：{tools.list_tools()}")
    return agent

async def interactive_loop(agent: AgentLoop) -> None:
    """交互式循环"""
    print("\n输入消息开始对话，输入 /exit 退出，/clear 清空历史，/tools 查看工具")

    while True:
        try:
            user_input = input("\n> ").strip()
        except KeyboardInterrupt:
            print("\n退出")
            break

        if not user_input:
            continue

        if user_input == "/exit":
            print("再见!")
            break

        if user_input == "/clear":
            agent.clear_history()
            print("历史已清空")
            continue

        if user_input == "/tools":
            print(f"可用工具：{agent.tools.list_tools()}")
            continue

        response = await agent.run(user_input)
        print(f"\n{response}")

def main() -> None:
    """主入口"""
    print("=" * 50)
    print("  NanoClaw - 智能编程助手")
    print("=" * 50)

    config = load_config()
    bus = MessageBus()

    asyncio.run(_run(config, bus))

async def _run(config, bus) -> None:
    """异步运行主体：连接 MCP → 启动渠道/网关 → 关闭 MCP。"""
    # 连接 MCP 服务器并发现工具
    mcp_manager = None
    mcp_tools: list = []
    if config.mcp_servers:
        mcp_manager = MCPClientManager(config.mcp_servers)
        await mcp_manager.connect_all()
        mcp_tools = mcp_manager.get_tools()

    # 定义 Agent 工厂函数
    def create_agent(session_key: str) -> AgentLoop:
        return build_agent(config, session_key, mcp_tools=mcp_tools)

    # 注册渠道
    cli_channel = CLIChannel(bus)
    cli_channel.session_key = "cli:local"  # 与下方预建 Agent 的 key 对应，避免消息被路由到错误会话
    channels = [
        cli_channel,
        FeishuChannel(bus, config.feishu_app_id, config.feishu_app_secret),
        QQChannel(bus, config),
        WebChannel(bus),
    ]

    # 启动网关
    gateway = Gateway(bus, channels, create_agent)

    # 预创建 CLI Agent，让初始化信息在启动时就显示
    cli_session_key = "cli:local"
    agent = create_agent(cli_session_key)
    gateway._agents[cli_session_key] = agent

    # 注入工具列表和清空回调给 CLI 渠道
    cli_channel.tool_names = agent.tools.list_tools()
    cli_channel._clear_callback = lambda: agent.clear_history()

    await gateway.run()

    # 关闭 MCP 连接
    if mcp_manager is not None:
        await mcp_manager.shutdown()

if __name__ == "__main__":
    main()