"""
记忆压缩模块

用于在对话历史过长时进行摘要压缩，保持 Token 预算。
"""

import json
import os
from datetime import datetime

from providers.base import LLMProvider

class MemoryConsolidator:
    """
    记忆压缩器。

    当对话历史超过 Token 预算时，将旧消息压缩为摘要，
    保留重要信息的同时减少 Token 消耗。
    """

    KEEP_LAST_MESSAGES = 6  # 保留最近的消息数

    def __init__(
        self,
        provider: LLMProvider,
        workspace: str,
        token_budget: int = 6000,
        skills_summary: str = "",
        max_tokens: int = 4000,
        consolidation_threshold: int = 8000
    ):
        """
        初始化记忆压缩器。

        Args:
            provider: LLM 提供方实例（用于生成摘要）
            workspace: 工作区路径（用于写入 HISTORY.md）
            skills_summary: 技能摘要（用于在压缩时包含技能信息）
            token_budget: Token 预算上限
            max_tokens: 最大 Token 数（用于压缩时的截断）
            consolidation_threshold: 压缩阈值（Token 数超过此值时触发压缩）
        """
        self.provider = provider
        self.workspace = workspace
        self.token_budget = token_budget
        self.skills_summary = skills_summary
        self.max_tokens = max_tokens
        self.consolidation_threshold = consolidation_threshold

    def estimate_tokens(self, messages: list[dict]) -> int:
        """
        估算消息列表的 Token 数量。

        使用简单的估算方法：字符数 / 2（中文约 1.5 字符/token）。

        Args:
            messages: 消息列表

        Returns:
            估算的 Token 数量
        """
        total_chars = 0
        for msg in messages:
            # 使用 ensure_ascii=False 支持中文
            total_chars += len(json.dumps(msg, ensure_ascii=False))
        return total_chars // 2

    async def maybe_consolidate(self, messages: list[dict]) -> list[dict]:
        """
        检查并执行记忆压缩。

        如果 Token 数量在预算内，直接返回原消息列表。
        否则压缩旧消息为摘要。

        Args:
            messages: 当前消息列表

        Returns:
            可能经过压缩的消息列表
        """
        # 检查是否需要压缩
        current_tokens = self.estimate_tokens(messages)
        if current_tokens <= self.token_budget or current_tokens <= self.consolidation_threshold:
            return messages

        # 需要压缩
        # 保留第一条（system prompt）和最后 6 条
        if len(messages) <= 1 + self.KEEP_LAST_MESSAGES:
            # 消息太少，无法压缩
            return messages

        system_msg = messages[0]
        recent_msgs = messages[-self.KEEP_LAST_MESSAGES:]
        old_msgs = messages[1:-self.KEEP_LAST_MESSAGES]

        if not old_msgs:
            return messages

        # 生成摘要
        summary = await self._summarize(old_msgs)

        # 包含技能摘要信息
        if self.skills_summary:
            summary += f"\n\n## 可用技能\n{self.skills_summary}"
        # 创建摘要消息
        summary_msg = {
            "role": "system",
            "content": f"[历史摘要]: {summary}"
        }

        # 保存到 HISTORY.md
        self._save_to_history(summary, len(old_msgs))

        # 组合压缩后的消息列表
        consolidated = [system_msg, summary_msg] + recent_msgs
        return consolidated

    async def _summarize(self, messages: list[dict]) -> str:
        """
        使用 LLM 生成消息摘要。

        Args:
            messages: 待压缩的消息列表

        Returns:
            摘要文本
        """
        # 拼接旧消息为文本
        conversation_text = ""
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # 简化 tool 相关消息的显示
            if role == "tool":
                tool_call_id = msg.get("tool_call_id", "unknown")
                conversation_text += f"[tool {tool_call_id}]: {content[:200]}...\n"
            else:
                conversation_text += f"[{role}]: {content}\n"

        # 构造摘要请求
        summary_prompt = f"""请用 3-5 句话概括以下对话的关键信息，保留重要的事实和结论，省略过程细节和寒暄。只输出摘要，不要其他内容。

对话内容：
{conversation_text}"""

        try:
            response = await self.provider.chat(
                messages=[{"role": "user", "content": summary_prompt}],
                tools=None  # 不需要工具调用
            )
            return response.content or "（摘要生成失败，旧消息已丢弃）"
        except Exception:
            return "（摘要生成失败，旧消息已丢弃）"

    def _save_to_history(self, summary: str, original_count: int) -> None:
        """
        将摘要保存到 HISTORY.md 文件。

        Args:
            summary: 摘要文本
            original_count: 原始消息数量
        """
        # 确保 memory 目录存在
        memory_dir = os.path.join(self.workspace, "memory")
        os.makedirs(memory_dir, exist_ok=True)

        history_path = os.path.join(memory_dir, "HISTORY.md")

        # 格式化内容
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"## {current_time}\n压缩了 {original_count} 条旧消息\n\n{summary}\n\n---\n"

        # 追加写入
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(entry)