"""
OpenAI 兼容 Provider 模块

适配 OpenAI API 格式的 LLM 提供方（如硅基流动、DeepSeek 等）。
"""

import json
from typing import Any

from openai import AsyncOpenAI, APIError

from providers.base import LLMProvider, LLMResponse, ToolCallRequest

class OpenAICompatProvider(LLMProvider):
    """
    OpenAI 兼容的 LLM 提供方。

    使用 OpenAI SDK 与兼容 OpenAI API 格式的服务通信。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str
    ):
        """
        初始化 OpenAI 兼容 Provider。

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model: 模型名称
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        model: str | None = None
    ) -> LLMResponse:
        """
        发送聊天请求。

        Args:
            messages: 消息列表，格式参考 OpenAI API
            tools: 工具定义列表（OpenAI Function Calling 格式）
            model: 模型名称（可选，默认使用构造时的 model）

        Returns:
            LLMResponse: LLM 响应
        """
        use_model = model or self.model

        try:
            # 动态构建请求参数
            # 关键：只有在 tools 不为空时才传 tools 和 tool_choice
            request_params: dict[str, Any] = {
                "model": use_model,
                "messages": messages
            }

            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = "auto"

            # 调用 API
            response = await self.client.chat.completions.create(**request_params)

            # 提取响应内容
            message = response.choices[0].message
            content = message.content

            # 提取 usage 信息
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }

            # 提取 finish_reason
            finish_reason = response.choices[0].finish_reason or "stop"

            # 转换 tool_calls
            tool_calls = []
            if message.tool_calls:
                # 先检查 message 顶层的 reasoning_content（某些模型放在这里）
                message_reasoning = getattr(message, "reasoning_content", None)

                for tc in message.tool_calls:
                    # 解析 arguments JSON
                    try:
                        arguments = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                    # 用 getattr 容错获取 reasoning_content
                    # 可能在 tool_call 上，也可能在 message 上
                    reasoning_content = getattr(tc, "reasoning_content", None)
                    if reasoning_content is None and message_reasoning:
                        reasoning_content = message_reasoning

                    tool_calls.append(ToolCallRequest(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                        reasoning_content=reasoning_content
                    ))

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage
            )

        except APIError as e:
            # API/业务错误（402 余额不足、403 模型禁用等）：不炸掉，包装成错误响应返回
            status = getattr(e, "status_code", None)
            detail = f" (HTTP {status})" if status else ""
            return LLMResponse(
                content=f"API 调用错误{detail}: {str(e)}",
                tool_calls=[],
                finish_reason="error",
                usage={}
            )
        # 其他异常（编程错误、本地异常）不在这里吞掉，直接抛出便于排查