import os
from datetime import datetime

class ContextBuilder:
    """上下文构建器，用于生成 LLM 所需的完整上下文信息"""

    DEFAULT_IDENTITY = """你是一个智能编程助手，专注于帮助用户完成代码开发任务。"""

    def __init__(
        self,
        workspace: str,
        identity_file: str = "identity.md",
        skills_summary: str = ""
    ) -> None:
        self.workspace = os.path.abspath(workspace)
        self.identity_file = identity_file
        self.skills_summary = skills_summary

    def _load_identity(self) -> str:
        """加载人设文件内容"""
        identity_path = os.path.join(self.workspace, self.identity_file)
        if os.path.isfile(identity_path):
            try:
                with open(identity_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except FileNotFoundError:
                pass
        return self.DEFAULT_IDENTITY

    def _load_memory(self) -> str:
        """加载长期记忆（预留接口）"""
        memory_path = os.path.join(self.workspace, "workspace", "memory", "MEMORY.md")
        if os.path.isfile(memory_path):
            try:
                with open(memory_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except FileNotFoundError:
                pass
        return ""

    def _memory_instructions(self) -> str:
        return """
        \n\n## 记忆管理指引
        当你在对话中发现以下类型的重要信息时，使用 write_file 工具更新 工作目录下的workspace/memory/MEMORY.md：
        - 用户的姓名、职业、技术偏好
        - 用户的项目信息和工作习惯
        - 用户明确要求你记住的事情
        - 用户纠正过你的错误（避免下次再犯）

更新时读取现有内容，在末尾追加新条目，保持 Markdown 列表格式。
不要记录琐碎的对话细节，只记录长期有价值的信息。
"""
    
    def build_system_prompt(self) -> str:
        """
        构建完整的 System Prompt

        包含：人设、当前时间、工作区路径、长期记忆
        """
        identity = self._load_identity()
        memory = self._load_memory()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")

        parts = [
            identity,
            f"当前时间：{current_time}",
            f"工作区路径：{self.workspace}"
        ]

         # ★ 重要：长期记忆
        if memory:
            parts.append(f"\n\n## 长期记忆\n以下是你对用户的已有了解：\n{memory}")
        parts.append(self._memory_instructions())   # ★ 记忆更新指引

        result = "\n\n".join(parts)

        # 追加技能摘要
        if self.skills_summary:
            result += f"\n\n## 可用技能\n{self.skills_summary}"

        return result

    def build_messages(
        self,
        history: list[dict] | None = None,
        current_message: str = ""
    ) -> list[dict]:
        """
        构建完整的消息列表

        Args:
            history: 历史对话记录，每条记录为 {"role": "user/assistant", "content": "..."}
            current_message: 当前用户消息

        Returns:
            list[dict]: 完整的消息列表
        """
        messages = [
            {"role": "system", "content": self.build_system_prompt()}
        ]

        if history:
            messages.extend(history)

        if current_message:
            messages.append({"role": "user", "content": current_message})

        return messages