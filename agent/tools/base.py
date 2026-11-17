"""Agent 工具基类模块。"""

from abc import ABC, abstractmethod


class Tool(ABC):
    """工具抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """工具参数定义（JSON Schema）"""
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """执行工具"""
        ...

    def to_function_definition(self) -> dict:
        """生成 OpenAI Function Calling 格式的工具定义"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }