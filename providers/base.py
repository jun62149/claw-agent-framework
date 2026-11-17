"""LLM Provider 基类模块。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRequest:
    """工具调用请求"""
    id: str
    name: str
    arguments: dict
    reasoning_content: str | None = None


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str | None
    tool_calls: list[ToolCallRequest]
    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        """是否包含工具调用"""
        return bool(self.tool_calls)


class LLMProvider(ABC):
    """LLM 提供方抽象基类"""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        model: str | None = None
    ) -> LLMResponse:
        """
        发送聊天请求

        Args:
            messages: 消息列表，格式参考 OpenAI API
            tools: 工具定义列表（OpenAI Function Calling 格式）
            model: 模型名称（可选）

        Returns:
            LLMResponse: LLM 响应
        """
        pass