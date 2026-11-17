from agent.tools.base import Tool

class ToolRegistry:
    """
    工具注册表，用于管理 Agent 可用的所有工具。

    提供工具注册、获取定义列表、执行工具等功能。
    内部使用字典存储工具实例，以工具名称为键。

    使用示例:
        registry = ToolRegistry()
        registry.register(GetWeatherTool())
        
        # 获取所有工具定义（用于 OpenAI API）
        definitions = registry.get_definitions()
        
        # 执行工具
        result = await registry.execute("get_weather", {"city": "北京"})
    """

    def __init__(self):
        """初始化空的工具注册表。"""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """
        注册一个工具到注册表。

        使用工具的 name 属性作为键存储工具实例。
        如果同名工具已存在，将被新工具覆盖。

        Args:
            tool: 要注册的工具实例，必须是 Tool 基类的子类。
        """
        self._tools[tool.name] = tool

    def get_definitions(self) -> list[dict]:
        """
        获取所有已注册工具的 OpenAI Function Calling 格式定义。

        遍历所有已注册的工具，调用每个工具的 to_function_definition()
        方法生成对应的 JSON 定义。

        Returns:
            包含所有工具定义的字典列表，可直接用于 OpenAI API 的 tools 参数。
        """
        return [tool.to_function_definition() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict) -> str:
        """
        根据工具名称执行指定工具。

        在注册表中查找指定名称的工具，并使用提供的参数异步执行。
        如果工具不存在或执行过程中发生异常，返回相应的错误信息。

        Args:
            name: 要执行的工具名称。
            arguments: 传递给工具执行方法的参数字典。

        Returns:
            工具执行成功的结果字符串，或错误信息字符串。
        """
        tool = self._tools.get(name)
        if tool is None:
            return f"错误：未找到工具 '{name}'"

        try:
            return await tool.execute(**arguments)
        except Exception as e:
            return f"错误：工具 '{name}' 执行失败 - {str(e)}"

    def list_tools(self) -> list[str]:
        """
        获取所有已注册工具的名称列表。

        Returns:
            已注册工具名称的字符串列表，按注册顺序排列（Python 3.7+ 字典保持插入顺序）。
        """
        return list(self._tools.keys())