"""
会话管理模块

用于持久化和恢复对话会话。
"""

import json
import os
from datetime import datetime
from pathlib import Path

class SessionManager:
    """
    会话管理器。

    管理对话历史记录的持久化存储，支持多会话隔离。
    每个会话以 JSONL 格式存储，每行一条消息记录。
    所有数据文件存储在 workspace/ 目录下。
    """

    def __init__(self, sessions_dir: str = "workspace/sessions"):
        """
        初始化会话管理器。

        Args:
            sessions_dir: 会话文件存储目录，默认为 "workspace/sessions"
        """
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)

    def _get_session_path(self, session_key: str) -> str:
        """
        获取会话文件路径。

        将 session_key 中的 ":" 替换为 "_"，生成安全的文件名。

        Args:
            session_key: 会话标识符

        Returns:
            会话文件的完整路径
        """
        safe_key = session_key.replace(":", "_")
        return os.path.join(self.sessions_dir, f"{safe_key}.jsonl")

    def save_message(self, session_key: str, message: dict) -> None:
        """
        保存一条消息到会话文件。

        自动添加时间戳，以追加模式写入 JSONL 文件。

        Args:
            session_key: 会话标识符
            message: 消息字典，包含 role 和 content
        """
        session_path = self._get_session_path(session_key)

        # 添加时间戳
        message_with_timestamp = message.copy()
        message_with_timestamp["timestamp"] = datetime.now().isoformat()

        # 追加写入 JSONL 文件（ensure_ascii=False 支持中文）
        with open(session_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message_with_timestamp, ensure_ascii=False) + "\n")

    def get_history(self, session_key: str) -> list[dict]:
        """
        获取会话的历史消息列表。

        读取 JSONL 文件并解析每行消息，去除时间戳字段。

        Args:
            session_key: 会话标识符

        Returns:
            消息列表，每条消息包含 role 和 content（不含 timestamp）
        """
        session_path = self._get_session_path(session_key)

        if not os.path.exists(session_path):
            return []

        messages = []
        with open(session_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    message = json.loads(line)
                    # 移除 timestamp 字段（OpenAI API 不认识）
                    message.pop("timestamp", None)
                    messages.append(message)
                except json.JSONDecodeError:
                    # 跳过无法解析的行
                    continue

        return messages

    def clear(self, session_key: str) -> None:
        """
        清除指定会话的历史记录。

        删除对应的 JSONL 文件。

        Args:
            session_key: 会话标识符
        """
        session_path = self._get_session_path(session_key)

        if os.path.exists(session_path):
            os.remove(session_path)

    def list_sessions(self) -> list[str]:
        """
        列出所有已存在的会话。

        扫描 sessions_dir 下的所有 .jsonl 文件。

        Returns:
            session_key 列表
        """
        sessions = []
        sessions_path = Path(self.sessions_dir)

        if not sessions_path.exists():
            return sessions

        for file_path in sessions_path.glob("*.jsonl"):
            # 从文件名还原 session_key
            session_key = file_path.stem
            sessions.append(session_key)

        return sessions