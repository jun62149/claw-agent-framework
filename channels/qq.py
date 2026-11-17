"""QQ 渠道实现模块。"""

import asyncio
import os
import re
from logging.handlers import TimedRotatingFileHandler
from typing import Any

import botpy
from botpy.message import GroupMessage, C2CMessage

from bus.queue import InboundMessage, MessageBus, OutboundMessage
from .base import Channel
from config import NanoClawConfig as Config

class QQBotClient(botpy.Client):
    """QQ Bot 客户端，处理消息接收事件。"""

    def __init__(self, channel: "QQChannel", *args, **kwargs):
        """初始化 QQ Bot 客户端。

        Args:
            channel: QQChannel 实例，用于发布消息到总线
        """
        super().__init__(*args, **kwargs)
        self._channel = channel

    async def on_group_at_message_create(self, message: GroupMessage):
        """处理群内 @消息事件。

        Args:
            message: 群消息对象
        """
        try:
            # 提取消息信息
            sender_id = message.author.member_openid
            chat_id = message.group_openid
            content = message.content.strip()

            # 去掉 @Bot 的前缀
            content = re.sub(r"<@!\d+>", "", content).strip()

            # 跳过空消息
            if not content:
                return

            print(f"[QQChannel] 群消息: sender={sender_id} chat={chat_id} content={content}")

            # 构造入站消息
            inbound = InboundMessage(
                channel="qq",
                sender_id=sender_id,
                chat_id=chat_id,
                content=content,
                raw={
                    "message_id": message.id,
                    "group_openid": chat_id,
                    "msg_type": "group",
                    "timestamp": message.timestamp,
                },
            )

            # 发布到总线
            await self._channel.bus.publish_inbound(inbound)

        except Exception as e:
            import traceback
            print(f"[QQChannel] 群消息处理异常: {e}")
            traceback.print_exc()

    async def on_c2c_message_create(self, message: C2CMessage):
        """处理 C2C 单聊消息事件。

        Args:
            message: C2C 消息对象
        """
        try:
            # 提取消息信息
            sender_id = message.author.user_openid
            chat_id = sender_id  # 单聊的 chat_id 就是对方的 openid
            content = message.content.strip()

            # 跳过空消息
            if not content:
                return

            print(f"[QQChannel] C2C消息: sender={sender_id} content={content}")

            # 构造入站消息
            inbound = InboundMessage(
                channel="qq",
                sender_id=sender_id,
                chat_id=chat_id,
                content=content,
                raw={
                    "message_id": message.id,
                    "user_openid": sender_id,
                    "msg_type": "c2c",
                    "timestamp": message.timestamp,
                },
            )

            # 发布到总线
            await self._channel.bus.publish_inbound(inbound)

        except Exception as e:
            import traceback
            print(f"[QQChannel] C2C消息处理异常: {e}")
            traceback.print_exc()

class QQChannel(Channel):
    """QQ 渠道，通过 QQ Bot API 接收和发送消息。"""

    def __init__(self, bus: MessageBus, config: Config):
        """初始化 QQ 渠道。

        Args:
            bus: 消息总线实例
            config: 配置对象，包含 app_id 和 app_secret
        """
        super().__init__(name="qq", bus=bus)
        self.app_id = config.qq_app_id
        self.app_secret = config.qq_app_secret
        self._bot: QQBotClient | None = None
        self._running = False

    async def start(self) -> None:
        """启动 QQ Bot 客户端，监听消息事件。"""
        # 未配置凭据时跳过，避免空 appid/secret 启动导致崩溃并拖垮网关
        if not self.app_id or not self.app_secret:
            print("[QQChannel] 未配置 QQ_APP_ID / QQ_APP_SECRET，跳过 QQ 启动")
            return

        # 配置 intents（意图）
        intents = botpy.Intents(
            public_messages=True,  # 群/C2C 消息（包含 on_group_at_message_create 和 on_c2c_message_create）
        )

        # 创建 Bot 客户端
        # timeout=30：覆盖 botpy 默认的 5 秒 HTTP 超时，避免国内网络偶发抖动导致登录失败
        # ext_handlers：把 botpy 默认写进 CWD 的 botpy.log 重定向到 logs/ 目录
        log_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "botpy.log"
        )
        self._bot = QQBotClient(
            channel=self,
            intents=intents,
            timeout=30,
            ext_handlers=[
                {
                    "handler": TimedRotatingFileHandler,
                    "level": "INFO",
                    "encoding": "utf-8",
                    "format": "%(asctime)s\t[%(levelname)s]\t(%(filename)s:%(lineno)s)%(funcName)s\t%(message)s",
                    "when": "D",
                    "interval": 1,
                    "backupCount": 7,
                    "filename": log_path,
                }
            ],
        )

        self._running = True
        print("[QQChannel] 正在启动 QQ Bot...")

        # 使用 async with + await start() 启动
        # botpy 的 start() 参数是 appid 和 secret（不是 token）
        try:
            async with self._bot:
                await self._bot.start(appid=self.app_id, secret=self.app_secret)
        except Exception as e:
            msg = str(e)
            # 网络超时/无法连接官方服务器的预期错误：简洁提示，不刷 traceback
            if "NoneType" in msg or "not subscriptable" in msg or "timeout" in msg.lower() or "connect" in msg.lower():
                print("[QQChannel] 连接 QQ 官方服务器超时，QQ 机器人本次未上线（不影响 CLI 使用）")
            else:
                import traceback
                print(f"[QQChannel] Bot 启动异常（已忽略，不影响其他渠道）：{e}")
                traceback.print_exc()

    async def send(self, message: OutboundMessage) -> None:
        """发送消息到 QQ。

        Args:
            message: 出站消息实例
        """
        # api 为 None 表示 bot 登录失败（例如网络超时未上线），此时不可发送
        if self._bot is None or not hasattr(self._bot, 'api') or self._bot.api is None:
            print("[QQChannel] Bot 未成功上线，无法发送消息")
            return

        try:
            # 根据 raw 中的 msg_type 判断是群消息还是 C2C 消息
            # Gateway 的 OutboundMessage 中没有 raw，需要通过 chat_id 格式推断
            # 或者我们用一个简单的策略：先尝试 C2C，失败再尝试群

            # 尝试发送 C2C 消息
            try:
                await self._bot.api.post_c2c_message(
                    openid=message.chat_id,
                    msg_type=0,  # 文本消息
                    msg_id="",
                    content=message.content,
                )
                print(f"[QQChannel] C2C消息已发送到 {message.chat_id}")
                return
            except Exception:
                pass

            # 尝试发送群消息
            await self._bot.api.post_group_message(
                group_openid=message.chat_id,
                msg_type=0,  # 文本消息
                msg_id="",
                content=message.content,
            )
            print(f"[QQChannel] 群消息已发送到 {message.chat_id}")

        except Exception as e:
            import traceback
            print(f"[QQChannel] 发送消息异常: {e}")
            traceback.print_exc()

    async def stop(self) -> None:
        """停止 QQ Bot 客户端连接。"""
        self._running = False
        if self._bot is not None:
            self._bot = None
            print("[QQChannel] Bot 已停止")