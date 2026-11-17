import json

from providers.base import LLMProvider, LLMResponse
from .tools.registry import ToolRegistry
from .context import ContextBuilder

class AgentLoop:
    """Agent 执行循环

    管理 LLM 与工具之间的交互循环，包含防爆检测机制。
    """

    # 防爆阈值常量
    FUSE_THRESHOLD = 20  # 熔断阈值
    WARNING_THRESHOLD = 10  # 警告阈值
    WINDOW_SIZE = 30  # 滑动窗口大小

    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry,
        context: ContextBuilder,
        model: str | None = None,
        session_key: str | None = None,
        max_iterations: int = 32,
        consolidator: "MemoryConsolidator | None" = None
    ):
        """初始化 AgentLoop

        Args:
            provider: LLM 提供方实例
            tools: 工具注册表
            context: 上下文构建器
            model: 模型名称（可选）
            max_iterations: 最大迭代次数
            consolidator: 记忆压缩器实例（可选）
        """
        self.session_key = session_key
        self.provider = provider
        self.tools = tools
        self.context = context
        self.model = model
        self.max_iterations = max_iterations

        # 内部状态
        self._tool_call_history: list[str] = []  # 滑动窗口
        self._session_history: list[dict] = []  # 对话历史
        self.consolidator = consolidator

    async def run(self, user_message: str) -> str:
        """执行 Agent 主循环

        Args:
            user_message: 用户输入消息

        Returns:
            str: Agent 的最终响应
        """
        # 1. 构建初始 messages
        messages = self.context.build_messages(
            history=self._session_history,
            current_message=user_message
        )

        # 2. 循环处理
        for _ in range(self.max_iterations):
            if hasattr(self, 'consolidator') and self.consolidator:
                messages = await self.consolidator.maybe_consolidate(messages)
            # a. 调用 LLM
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            # a. 检查错误   
            if response.finish_reason == "error":
                return f"抱歉，发生了错误，请稍后重试。"

            # c. 处理工具调用
            if response.has_tool_calls:
                # 构造 assistant 消息（含 tool_calls）
                assistant_msg = self._build_assistant_message(response)
                messages.append(assistant_msg)

                # 遍历每个 tool_call
                for tc in response.tool_calls:
                    # 获取参数 JSON 字符串
                    args_json = json.dumps(tc.arguments, ensure_ascii=False)
                    print(f"\n🛠️ 调用工具：{tc.name}，参数：{args_json}")

                    # 防爆检测
                    check_result = self._check_tool_loop(tc.name, args_json)

                    if check_result and "熔断" in check_result:
                        # 熔断 - 直接返回
                        print(f"⛔ {check_result}")
                        return check_result
                    elif check_result and "警告" in check_result:
                        # 警告 - append SYSTEM_ERROR 消息，skip 执行
                        print(f"⚠️ {check_result}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"系统警告：{check_result}"
                        })
                    else:
                        # 防爆通过 - 执行工具
                        result = await self.tools.execute(tc.name, tc.arguments)
                        result_preview = (result[:200] + "…") if len(result) > 200 else result
                        print(f"📦 执行结果：{result_preview}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result
                        })

                # continue 回到循环顶部
                continue

            # d. 没有工具调用 - 保存历史并返回
            self._save_to_history(messages)
            return response.content or ""

        # 3. for-else: 超过最大次数
        return "已达到最大迭代次数，任务未完成。"

    def _build_assistant_message(self, response: LLMResponse) -> dict:
        """构建 assistant 消息（含 tool_calls）

        严格按照 OpenAI 格式构建，reasoning_content 放在顶层。

        Args:
            response: LLM 响应

        Returns:
            dict: assistant 消息字典
        """
        assistant_msg: dict = {
            "role": "assistant",
            "content": response.content
        }

        # 构建 tool_calls 数组
        tool_calls = []
        for tc in response.tool_calls:
            tool_call_item = {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                }
            }
            tool_calls.append(tool_call_item)

        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls

        # reasoning_content 放在顶层（不能放在 tool_calls 里）
        if response.tool_calls and response.tool_calls[0].reasoning_content:
            assistant_msg["reasoning_content"] = response.tool_calls[0].reasoning_content

        return assistant_msg

    def _check_tool_loop(self, tool_name: str, tool_args_json: str) -> str | None:
        """防爆检测

        检测工具调用的重复频率，防止无限循环。

        Args:
            tool_name: 工具名称
            tool_args_json: 工具参数的 JSON 字符串

        Returns:
            str | None: 熔断/警告消息，或 None 表示放行
        """
        signature = f"{tool_name}:{tool_args_json}"

        # 先累计再判断，否则警告后不加、计数永远到不了熔断阈值
        self._tool_call_history.append(signature)

        # 维护滑动窗口大小
        if len(self._tool_call_history) > self.WINDOW_SIZE:
            self._tool_call_history.pop(0)

        # 统计签名出现次数（含本次）
        count = self._tool_call_history.count(signature)

        if count >= self.FUSE_THRESHOLD:
            return f"检测到工具 '{tool_name}' 重复调用已达熔断阈值（{self.FUSE_THRESHOLD}次），已自动终止执行。请尝试其他方案。"
        elif count >= self.WARNING_THRESHOLD:
            return f"警告：工具 '{tool_name}' 重复调用已达 {self.WARNING_THRESHOLD} 次，请检查是否有循环调用问题。"

        return None

    def _save_to_history(self, messages_snapshot: list[dict]) -> None:
        """保存本轮新增消息到会话历史

        Args:
            messages_snapshot: 当前完整的消息列表
        """
        # 计算新增消息（跳过 system 消息）
        # 新消息数量 = 总消息数 - 已有历史消息数 - 1 (system)
        existing_count = len(self._session_history)

        # 新增的消息（不包含 system）
        new_messages = messages_snapshot[1 + existing_count:]

        # 添加到历史
        self._session_history.extend(new_messages)

    def clear_history(self) -> None:
        """清空对话历史和工具调用历史"""
        self._tool_call_history.clear()
        self._session_history.clear()