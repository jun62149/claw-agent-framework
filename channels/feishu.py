"""飞书渠道实现模块。"""

import asyncio
import json
import os
import re
import threading
import traceback
from typing import Any

import lark_oapi as lark
import lark_oapi.api.im.v1 as im_v1

from bus.queue import InboundMessage, MessageBus, OutboundMessage
from .base import Channel

class FeishuChannel(Channel):
    """飞书渠道，通过 WebSocket 接收消息并通过 API 发送回复。"""

    def __init__(self, bus: MessageBus, app_id: str, app_secret: str):
        """初始化飞书渠道。

        Args:
            bus: 消息总线实例
            app_id: 飞书 App ID
            app_secret: 飞书 App Secret
        """
        super().__init__(name="feishu", bus=bus)
        self.app_id = app_id
        self.app_secret = app_secret
        self._client: Any = None
        self._lark_api_client: Any = None  # 用于发送消息的 API 客户端
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None  # 保存主事件循环引用

    async def start(self) -> None:
        """启动飞书 WebSocket 客户端，监听消息事件。"""
        # 未配置凭据时跳过，避免用空 appid/secret 连接导致崩溃并拖垮网关
        if not self.app_id or not self.app_secret:
            print("[FeishuChannel] 未配置 FEISHU_APP_ID / FEISHU_APP_SECRET，跳过飞书启动")
            return

        # ★ 保存当前事件循环的引用，供 WebSocket 子线程回调使用
        self._loop = asyncio.get_running_loop()

        # 自动探测本地代理（Clash 等常见端口），供 SDK 的 WebSocket 连接使用。
        # 飞书 SDK 默认强制直连，若直连不通（握手超时），需要走本地代理才能连上。
        if not any(
            os.environ.get(v)
            for v in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")
        ):
            proxy = self._detect_local_proxy()
            if proxy:
                os.environ["HTTPS_PROXY"] = proxy
                os.environ["HTTP_PROXY"] = proxy
                print(f"[FeishuChannel] 检测到本地代理 {proxy}，飞书 WebSocket 将通过该代理连接")

        # 创建用于发送消息的 API 客户端
        self._lark_api_client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

        # 创建事件处理器（使用 P2 版本协议）
        event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(self._on_message) \
            .build()

        # 创建 WebSocket 客户端
        self._client = lark.ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        # 注册连接状态回调：lark SDK 内部会自行捕获连接异常并无限重连，
        # 失败/断开时不会向外抛出，这里借回调让连接状态可见，避免"假在线"
        self._client.on_reconnecting = lambda: print(
            "[FeishuChannel] 与飞书的连接已断开，正在重连...（期间无法接收消息）"
        )
        self._client.on_reconnected = lambda: print("[FeishuChannel] 已连接飞书")

        self._running = True
        print("[FeishuChannel] 正在连接飞书 WebSocket...")

        # 启动 WebSocket 连接（lark 的 start 是长连接阻塞调用，会卡住事件循环）
        # 放到 daemon 线程里跑，主进程退出时该线程随之强制结束，保证程序能干净退出
        # 注：SDK 会自行吞掉连接异常并进入重连，故下面的 except 基本不会命中，仅作兜底
        try:
            thread = threading.Thread(
                target=self._client.start,
                daemon=True,
                name="feishu-ws",
            )
            thread.start()
        except Exception as e:
            print(f"[FeishuChannel] 飞书连接启动失败（已忽略，不影响其他渠道）：{e}")
            traceback.print_exc()

    @staticmethod
    def _detect_local_proxy() -> str | None:
        """探测本机常见代理软件的监听地址，返回代理 URL 或 None。

        依次尝试系统注册表里的代理设置以及常见 Clash 端口。
        注意：从 window 注册表读取系统代理仅用于探测；实际生效仍看环境变量。
        """
        candidates: list[str] = []

        # 1. 从系统注册表读取用户配置的代理
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            )
            try:
                proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
                if proxy_enable:
                    server, _ = winreg.QueryValueEx(key, "ProxyServer")
                    if server:
                        candidates.append(f"http://{server}" if "://" not in server else server)
            finally:
                winreg.CloseKey(key)
        except Exception:
            pass

        # 2. 常见代理默认端口
        candidates.extend(["http://127.0.0.1:7897", "http://127.0.0.1:7890", "http://127.0.0.1:10809", "http://127.0.0.1:1080"])

        # 3. 逐个探测端口是否开放
        import socket
        for url in candidates:
            try:
                host_port = url.split("://")[1]
                host, port = host_port.split(":")
                with socket.create_connection((host, int(port)), timeout=0.5):
                    return url
            except Exception:
                continue
        return None

    def _on_message(self, data: Any) -> None:
        """处理飞书消息接收事件（P2 协议）。

        注意：此方法在飞书 SDK 的 WebSocket 子线程中被调用，
        不能直接 await，需要通过 run_coroutine_threadsafe 投递到主事件循环。

        Args:
            data: 飞书 P2 事件回调数据
        """
        try:
            event = data.event
            # 提取消息信息
            sender_id = event.sender.sender_id.open_id
            chat_id = event.message.chat_id
            message_type = event.message.message_type
            sender_type = event.sender.sender_type

            print(f"[FeishuChannel] 收到消息 sender={sender_id} type={message_type} sender_type={sender_type}")

            # 过滤：忽略 Bot 自己发送的消息
            if sender_type == "app":
                return

            # 过滤：只处理文本消息
            if message_type != "text":
                return

            # 解析消息内容（飞书消息是 JSON 格式）
            content = json.loads(event.message.content)
            text = content.get("text", "")

            # 去掉 @Bot 的占位符（飞书群消息中为 @_user_N / @_all）
            # 只删这些占位符，避免误删正文中的普通 @（如邮箱 a@b.com）
            text = re.sub(r'@_user_\d+|@_all', "", text).strip()

            # 跳过空消息
            if not text:
                return

            print(f"[FeishuChannel] 解析文本: {text}")

            # 构造入站消息
            message = InboundMessage(
                channel="feishu",
                sender_id=sender_id,
                chat_id=chat_id,
                content=text,
                raw={
                    "sender_id": sender_id,
                    "chat_id": chat_id,
                    "message_type": message_type,
                    "content": content,
                },
            )

            # ★ 使用启动时保存的主事件循环引用，线程安全地投递
            if self._loop is not None and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.bus.publish_inbound(message),
                    self._loop,
                )
            else:
                print("[FeishuChannel] 警告: 主事件循环不可用，消息丢弃")

        except Exception as e:
            print(f"[FeishuChannel] 消息处理异常: {e}")
            traceback.print_exc()

    async def send(self, message: OutboundMessage) -> None:
        """发送消息到飞书。

        Args:
            message: 出站消息实例
        """
        if self._lark_api_client is None:
            print("[FeishuChannel] API 客户端未初始化，无法发送消息")
            return

        try:
            # 构造飞书消息请求
            request = im_v1.CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(
                    im_v1.CreateMessageRequestBody.builder()
                    .receive_id(message.chat_id)
                    .msg_type("text")
                    .content(json.dumps({"text": message.content}, ensure_ascii=False))
                    .build()
                ) \
                .build()

            # 发送消息（飞书 API 是同步的，用 asyncio.to_thread 包装）
            response = await asyncio.to_thread(
                self._lark_api_client.im.v1.message.create,
                request,
            )

            if not response.success():
                print(f"[FeishuChannel] 发送失败: code={response.code} msg={response.msg}")

        except Exception as e:
            print(f"[FeishuChannel] 发送消息异常: {e}")
            traceback.print_exc()

    async def stop(self) -> None:
        """停止飞书客户端连接。

        注意：lark SDK 未提供主动关闭长连接的接口，底层 WebSocket 线程
        只能随进程退出而结束；这里重置状态并注销回调，避免退出后继续打印重连日志。
        """
        self._running = False
        self._loop = None
        if self._client is not None:
            self._client.on_reconnecting = lambda: None
            self._client.on_reconnected = lambda: None
            self._client = None
        self._lark_api_client = None