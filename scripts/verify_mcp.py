"""Exercise real MCP stdio discovery/calls/cleanup without accessing memo data."""
import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.tools.mcp import MCPClientManager


async def main():
    manager = MCPClientManager({name: {
        "command": sys.executable,
        "args": [str(ROOT / f"mcp_servers/{name}_server.py")],
    } for name in ("memo", "poetry")})
    try:
        await manager.connect_all(timeout=10)
        tools = {tool.name: tool for tool in manager.get_tools()}
        assert len(tools) == 6, "Expected six example tools"
        assert "poetry__list_poets" in tools, "Tool discovery failed"
        result = await tools["poetry__list_poets"].execute()
        assert "诗人列表" in result, "Tool call failed"
        print("PASS: real stdio tool discovery, schema adaptation and invocation")
    finally:
        await manager.shutdown()
    print("PASS: shutdown returned (also inspect stderr for SDK cleanup errors)")


if __name__ == "__main__":
    asyncio.run(main())
