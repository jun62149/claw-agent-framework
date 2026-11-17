"""Gateway 模块，负责协调消息总线、渠道和 Agent 实例。"""

import asyncio
from typing import Callable

from bus.queue import InboundMessage, MessageBus, OutboundMessage
from channels.base import Channel
from agent.loop import AgentLoop

class Gateway:
    """网关类，协调消息路由和 Agent 生命周期。

    负责管理渠道启动、入站消息分发到 Agent、出站消息分发到渠道。
    """

    def __init__(
        self,
        bus: MessageBus,
        channels: list[Channel],
        agent_factory: Callable[[str], AgentLoop]
    ):
        """初始化网关。

        Args:
            bus: 消息总线实例
            channels: 渠道列表
            agent_factory: Agent 工厂函数，输入 session_key，返回 AgentLoop 实例
        """
        self.bus = bus
        self.channels = channels
        self.agent_factory = agent_factory

        # 内部状态
        self._agents: dict[str, AgentLoop] = {}  # 按 session_key 缓存 Agent
        self._channel_map: dict[str, Channel] = {ch.name: ch for ch in channels}  # 按渠道名索引

    async def run(self) -> None:
        """启动网关，并发运行所有渠道和消息处理循环。"""
        tasks = []

        # 启动所有渠道
        for channel in self.channels:
            tasks.append(asyncio.create_task(channel.start()))

        # 启动入站消费循环
        tasks.append(asyncio.create_task(self._process_inbound()))

        # 启动出站分发循环
        tasks.append(asyncio.create_task(self._dispatch_outbound()))

        # 任何一个渠道退出（如 CLI 的 /exit）即触发关闭
        # 等待关闭信号后取消所有任务
        try:
            await self.bus.wait_until_shutdown()
            await self.shutdown()
            for task in tasks:
                task.cancel()
        finally:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_inbound(self) -> None:
        """处理入站消息循环。

        从消息总线消费入站消息，分发给对应的 Agent 处理，
        并将响应发布到出站队列。
        """
        while True:
            try:
                # 从入站队列获取消息
                msg = await self.bus.consume_inbound()

                # 构造 session_key
                session_key = f"{msg.channel}:{msg.sender_id}"

                # 获取或创建 Agent
                if session_key not in self._agents:
                    self._agents[session_key] = self.agent_factory(session_key)

                agent = self._agents[session_key]

                # 调用 Agent 处理消息
                try:
                    response = await agent.run(msg.content)
                except Exception as e:
                    # Agent 出错时发送友好错误消息
                    response = f"抱歉，处理消息时发生错误：{str(e)}"

                # 构造出站消息并发布
                outbound = OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=response
                )
                await self.bus.publish_outbound(outbound)

            except Exception as e:
                # 捕获未预期的异常，避免循环崩溃
                print(f"[Gateway] 入站处理异常: {e}")

    async def _dispatch_outbound(self) -> None:
        """分发出站消息循环。

        从出站队列获取消息，根据渠道名分发给对应的渠道发送。
        """
        while True:
            try:
                # 从出站队列获取消息
                msg = await self.bus.consume_outbound()

                # 根据渠道名找到对应的 Channel
                channel = self._channel_map.get(msg.channel)
                if channel is None:
                    print(f"[Gateway] 未找到渠道: {msg.channel}")
                    continue

                # 调用渠道发送消息
                await channel.send(msg)

            except Exception as e:
                # 捕获未预期的异常，避免循环崩溃
                print(f"[Gateway] 出站分发异常: {e}")

    async def shutdown(self) -> None:
        """关闭网关，停止所有渠道并清理资源。"""
        # 停止所有渠道
        for channel in self.channels:
            try:
                await channel.stop()
            except Exception as e:
                print(f"[Gateway] 停止渠道 {channel.name} 时出错: {e}")

        # 清空 Agent 缓存
        self._agents.clear()