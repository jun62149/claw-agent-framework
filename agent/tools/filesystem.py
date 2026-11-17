import os
from agent.tools.base import Tool

class ReadFileTool(Tool):
    """
    读取本地文件内容的工具。

    支持读取文本文件，自动进行路径安全检查防止目录穿越。
    输出内容超过 16000 字符时会自动截断。

    Attributes:
        workspace: 工作区根目录的绝对路径，所有文件操作限制在此目录内。
    """

    def __init__(self, workspace: str):
        """
        初始化 ReadFileTool。

        Args:
            workspace: 工作区根目录路径，将被转换为绝对路径。
        """
        self.workspace = os.path.abspath(workspace)

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "读取指定路径的文本文件内容。路径必须在 workspace 目录内。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "相对于 workspace 的文件路径"
                }
            },
            "required": ["file_path"]
        }

    def _check_path(self, user_path: str) -> str | None:
        """
        检查并解析用户提供的相对路径。

        将用户路径与 workspace 拼接后解析为绝对路径，
        并验证最终路径是否在 workspace 目录内，防止目录穿越攻击。

        Args:
            user_path: 用户提供的相对路径。

        Returns:
            验证通过的绝对路径，或 None（路径非法）。
        """
        absolute_path = os.path.abspath(os.path.join(self.workspace, user_path))
        if not absolute_path.startswith(self.workspace):
            return None
        return absolute_path

    async def execute(self, file_path: str) -> str:
        """
        读取文件内容。

        Args:
            file_path: 相对于 workspace 的文件路径。

        Returns:
            文件内容字符串，超过 16000 字符会被截断。
            路径非法时返回错误信息，文件不存在时返回错误信息。
        """
        absolute_path = self._check_path(file_path)
        if absolute_path is None:
            return f"错误：路径 '{file_path}' 超出工作区范围，访问被拒绝"

        if not os.path.exists(absolute_path):
            return f"错误：文件 '{file_path}' 不存在"

        if not os.path.isfile(absolute_path):
            return f"错误：'{file_path}' 不是文件"

        try:
            with open(absolute_path, "r", encoding="utf-8") as f:
                content = f.read()
            if len(content) > 16000:
                content = content[:16000] + "\n... [内容已截断]"
            return content
        except Exception as e:
            return f"错误：读取文件失败 - {str(e)}"

class WriteFileTool(Tool):
    """
    写入文件内容的工具。

    支持创建新文件或覆盖现有文件，自动创建不存在的父目录。
    包含路径安全检查防止目录穿越。

    Attributes:
        workspace: 工作区根目录的绝对路径，所有文件操作限制在此目录内。
    """

    def __init__(self, workspace: str):
        """
        初始化 WriteFileTool。

        Args:
            workspace: 工作区根目录路径，将被转换为绝对路径。
        """
        self.workspace = os.path.abspath(workspace)

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "将内容写入指定路径的文件。路径必须在 workspace 目录内，自动创建父目录。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "相对于 workspace 的文件路径"
                },
                "content": {
                    "type": "string",
                    "description": "要写入文件的内容"
                }
            },
            "required": ["file_path", "content"]
        }

    def _check_path(self, user_path: str) -> str | None:
        """
        检查并解析用户提供的相对路径。

        将用户路径与 workspace 拼接后解析为绝对路径，
        并验证最终路径是否在 workspace 目录内，防止目录穿越攻击。

        Args:
            user_path: 用户提供的相对路径。

        Returns:
            验证通过的绝对路径，或 None（路径非法）。
        """
        absolute_path = os.path.abspath(os.path.join(self.workspace, user_path))
        if not absolute_path.startswith(self.workspace):
            return None
        return absolute_path

    async def execute(self, file_path: str, content: str) -> str:
        """
        写入文件内容。

        Args:
            file_path: 相对于 workspace 的文件路径。
            content: 要写入的内容。

        Returns:
            成功信息或错误信息。
        """
        absolute_path = self._check_path(file_path)
        if absolute_path is None:
            return f"错误：路径 '{file_path}' 超出工作区范围，访问被拒绝"

        try:
            parent_dir = os.path.dirname(absolute_path)
            os.makedirs(parent_dir, exist_ok=True)

            with open(absolute_path, "w", encoding="utf-8") as f:
                f.write(content)

            return f"成功：文件 '{file_path}' 已写入"
        except Exception as e:
            return f"错误：写入文件失败 - {str(e)}"

class ListDirTool(Tool):
    """
    列出目录内容的工具。

    显示目录下的所有文件和子目录，文件显示大小，目录显示 "/" 后缀。
    包含路径安全检查防止目录穿越，结果按名称排序。

    Attributes:
        workspace: 工作区根目录的绝对路径，所有文件操作限制在此目录内。
    """

    def __init__(self, workspace: str):
        """
        初始化 ListDirTool。

        Args:
            workspace: 工作区根目录路径，将被转换为绝对路径。
        """
        self.workspace = os.path.abspath(workspace)

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "列出指定目录的内容。显示文件大小或目录标记，结果按名称排序。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dir_path": {
                    "type": "string",
                    "description": "相对于 workspace 的目录路径，默认为空（列出根目录）"
                }
            },
            "required": []
        }

    def _check_path(self, user_path: str) -> str | None:
        """
        检查并解析用户提供的相对路径。

        将用户路径与 workspace 拼接后解析为绝对路径，
        并验证最终路径是否在 workspace 目录内，防止目录穿越攻击。

        Args:
            user_path: 用户提供的相对路径。

        Returns:
            验证通过的绝对路径，或 None（路径非法）。
        """
        absolute_path = os.path.abspath(os.path.join(self.workspace, user_path))
        if not absolute_path.startswith(self.workspace):
            return None
        return absolute_path

    async def execute(self, dir_path: str = "") -> str:
        """
        列出目录内容。

        Args:
            dir_path: 相对于 workspace 的目录路径，默认为空（根目录）。

        Returns:
            格式化的目录列表字符串，或错误信息。
        """
        absolute_path = self._check_path(dir_path)
        if absolute_path is None:
            return f"错误：路径 '{dir_path}' 超出工作区范围，访问被拒绝"

        if not os.path.exists(absolute_path):
            return f"错误：目录 '{dir_path}' 不存在"

        if not os.path.isdir(absolute_path):
            return f"错误：'{dir_path}' 不是目录"

        try:
            entries = os.listdir(absolute_path)
            entries.sort()

            if not entries:
                return "（空目录）"

            lines = []
            for entry in entries:
                entry_path = os.path.join(absolute_path, entry)
                if os.path.isdir(entry_path):
                    lines.append(f"{entry}/")
                else:
                    size = os.path.getsize(entry_path)
                    lines.append(f"{entry} ({self._format_size(size)})")

            return "\n".join(lines)
        except Exception as e:
            return f"错误：列出目录失败 - {str(e)}"

    def _format_size(self, size: int) -> str:
        """
        将字节大小格式化为人类可读的字符串。

        Args:
            size: 文件大小（字节）。

        Returns:
            格式化后的字符串，如 "1.5 KB"。
        """
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
            size /= 1024
        return f"{size:.1f} TB"