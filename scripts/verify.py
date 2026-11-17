"""Offline smoke checks. Run from any directory; never load local credentials."""
import asyncio
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.context import ContextBuilder
from agent.loop import AgentLoop
from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry
from agent.tools.filesystem import ReadFileTool, WriteFileTool
from agent.tools.shell import ExecTool
from bus.queue import InboundMessage, MessageBus
from gateway import Gateway
from providers.base import LLMResponse, ToolCallRequest
from providers.openai_compat import OpenAICompatProvider


class FakeProvider:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []

    async def chat(self, messages, **kwargs):
        self.requests.append(copy.deepcopy(messages))
        return next(self.replies)


class Echo(Tool):
    name = "echo"
    description = "Echo input"
    parameters = {"type": "object", "properties": {"text": {"type": "string"}}}

    async def execute(self, text):
        if text == "fail":
            raise ValueError("test failure")
        return text


class CoreChecks(unittest.IsolatedAsyncioTestCase):
    def agent(self, provider, workspace, **kwargs):
        registry = ToolRegistry()
        registry.register(Echo())
        return AgentLoop(provider, registry, ContextBuilder(workspace), **kwargs)

    async def test_multiround_tool_results_and_followup(self):
        provider = FakeProvider([
            LLMResponse(None, [ToolCallRequest("a", "echo", {"text": "one"}),
                               ToolCallRequest("b", "echo", {"text": "two"})]),
            LLMResponse(None, [ToolCallRequest("c", "echo", {"text": "three"})]),
            LLMResponse("done", []), LLMResponse("followup", []),
        ])
        with tempfile.TemporaryDirectory() as temp:
            agent = self.agent(provider, temp)
            self.assertEqual(await agent.run("start"), "done")
            results = [m for m in provider.requests[2] if m["role"] == "tool"]
            self.assertEqual([(m["tool_call_id"], m["content"]) for m in results],
                             [("a", "one"), ("b", "two"), ("c", "three")])
            self.assertEqual(await agent.run("again"), "followup")
            # Current implementation does not save the final assistant answer.
            self.assertTrue(any(m.get("content") == "start" for m in provider.requests[3]))
            agent.clear_history()
            self.assertEqual(agent._session_history, [])

    async def test_tool_errors(self):
        registry = ToolRegistry()
        registry.register(Echo())
        self.assertIn("未找到", await registry.execute("missing", {}))
        self.assertIn("执行失败", await registry.execute("echo", {"text": "fail"}))
        self.assertIn("执行失败", await registry.execute("echo", {}))

    async def test_limits(self):
        with tempfile.TemporaryDirectory() as temp:
            agent = self.agent(FakeProvider([LLMResponse(None, [ToolCallRequest("a", "echo", {"text": "x"})])]), temp, max_iterations=1)
            self.assertIn("最大迭代", await agent.run("start"))
            agent.clear_history()
            checks = [agent._check_tool_loop("echo", "{}") for _ in range(20)]
            self.assertIsNone(checks[8])
            self.assertIn("警告", checks[9])
            self.assertIn("熔断", checks[19])

    async def test_files_and_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertIn("成功", await WriteFileTool(temp).execute("hello.txt", "hello"))
            self.assertEqual(await ReadFileTool(temp).execute("hello.txt"), "hello")
            self.assertIn("退出码: 0", await ExecTool(temp).execute("echo smoke-ok"))
            self.assertIn("安全拦截", await ExecTool(temp).execute("sudo whoami"))

    async def test_gateway_routing(self):
        bus = MessageBus()
        created = []
        def factory(key):
            agent = SimpleNamespace(run=AsyncMock(return_value=key))
            created.append(agent)
            return agent
        gateway = Gateway(bus, [], factory)
        task = asyncio.create_task(gateway._process_inbound())
        try:
            for channel, sender in [("cli", "a"), ("web", "a"), ("cli", "a")]:
                await bus.publish_inbound(InboundMessage(channel=channel, sender_id=sender, chat_id="chat", content="hello"))
                result = await asyncio.wait_for(bus.consume_outbound(), 2)
                self.assertEqual(result.content, f"{channel}:{sender}")
            self.assertEqual(len(created), 2)
            self.assertEqual(created[0].run.await_count, 2)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_provider_json_parsing(self):
        provider = OpenAICompatProvider("test-only", "http://127.0.0.1:1", "test")
        message = SimpleNamespace(content=None, tool_calls=[SimpleNamespace(
            id="a", function=SimpleNamespace(name="echo", arguments='{"text":"ok"}'))])
        response = SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="tool_calls")], usage=None)
        provider.client.chat.completions.create = AsyncMock(return_value=response)
        try:
            result = await provider.chat([], tools=[Echo().to_function_definition()])
            self.assertEqual(result.tool_calls[0].arguments, {"text": "ok"})
            message.tool_calls[0].function.arguments = "invalid-json"
            self.assertEqual((await provider.chat([])).tool_calls[0].arguments, {})
        finally:
            await provider.client.close()


class WebChecks(unittest.TestCase):
    def test_web_page_and_websocket_bus(self):
        from channels.web import WebChannel
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from bus.queue import OutboundMessage
        bus = MessageBus()
        channel = WebChannel(bus)
        channel._app = FastAPI()
        channel._register_routes()
        with TestClient(channel._app) as client:
            self.assertEqual(client.get("/").status_code, 200)
            with client.websocket_connect("/ws") as ws:
                ws.send_text("hello")
                msg = client.portal.call(bus.consume_inbound)
                self.assertEqual(msg.content, "hello")
                client.portal.call(channel.send, OutboundMessage(channel="web", chat_id=msg.chat_id, content="reply"))
                self.assertEqual(ws.receive_text(), "reply")


if __name__ == "__main__":
    unittest.main(verbosity=2)
