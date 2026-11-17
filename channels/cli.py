"""CLI 渠道实现模块。"""

import asyncio
from typing import Callable

from bus.queue import InboundMessage, MessageBus, OutboundMessage
from .base import Channel

class CLIChannel(Channel):
    """命令行交互渠道。

    继承 Channel 基类，实现命令行界面的消息收发。
    使用 asyncio.Event 同步等待回复完成。
    """

    def __init__(self, bus: MessageBus):
        """初始化 CLI 渠道。

        Args:
            bus: 消息总线实例
        """
        super().__init__(name="cli", bus=bus)
        self._response_event = asyncio.Event()  # 用于同步等待回复

        # 预留属性，由 main.py 在创建后注入
        self.tool_names: list[str] = []  # 工具名列表
        self._clear_callback: Callable[[], None] | None = None  # 清空历史回调
        self.session_key: str | None = None  # 会话标识，格式为 "{channel}:{sender_id}" ，用于关联 AgentLoop

    async def start(self) -> None:
        """启动 CLI 渠道，循环读取用户输入。

        支持命令：
            /exit - 退出程序
            /clear - 清空历史（调用 _clear_callback）
            /tools - 列出可用工具（打印 tool_names）

        正常输入将构造 InboundMessage 并发布到消息总线，
        然后等待回复完成再继续下一轮输入。
        """
        while True:
            # 使用 asyncio.to_thread 包装阻塞的 input()
            user_input = await self._async_input("你> ")

            # 跳过空输入
            if not user_input.strip():
                continue

            # 处理命令
            if user_input.startswith("/"):
                command = user_input.strip().lower()
                if command == "/exit":
                    print("再见！")
                    self.bus.request_shutdown()  # 通知网关 worker 退出
                    break
                elif command == "/clear":
                    # 调用清空历史回调
                    if self._clear_callback:
                        self._clear_callback()
                    print("历史已清空")
                    continue
                elif command == "/tools":
                    # 打印工具列表
                    if self.tool_names:
                        print("可用工具列表：")
                        for name in self.tool_names:
                            print(f"  - {name}")
                    else:
                        print("当前没有可用工具")
                    continue
                else:
                    print(f"未知命令: {user_input}")
                    continue

            # 重置事件，准备等待回复
            self._response_event.clear()

            # 构造入站消息并发布
            message = InboundMessage(
                channel="cli",
                sender_id="local",  # Gateway 会拼成 "cli:local"，与预建 Agent 的 key 对应
                chat_id="direct",
                content=user_input,
            )
            await self.bus.publish_inbound(message)

            # 等待回复完成
            await self._response_event.wait()

    async def send(self, message: OutboundMessage) -> None:
        """发送出站消息到 CLI。

        Args:
            message: 出站消息实例
        """
        print(f"🤖 {message.content}")
        # 通知 start() 可以继续了
        self._response_event.set()

    async def _async_input(self, prompt: str = "") -> str:
        """异步包装同步的 input() 函数。

        Args:
            prompt: 输入提示符

        Returns:
            用户输入的字符串
        """
        return await asyncio.to_thread(input, prompt)