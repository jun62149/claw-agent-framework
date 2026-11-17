"""Shell 命令执行工具模块"""

import asyncio
import os
import re

from agent.tools.base import Tool

class ExecTool(Tool):
    """Shell 命令执行工具"""

    DENY_PATTERNS = [
        r"rm\s+.*-r",
        r"rm\s+-rf",
        r"rmdir\s+/s",
        r"format\s+",
        r"mkfs",
        r"\bshutdown\b",
        r"\breboot\b",
        r"sudo\s+",
        r"\bsu\b",
        r"chmod\s+777",
        r">\s*/dev/",
        r"wget\s+.*\|\s*sh",
        r"curl\s+.*\|\s*bash",
        r"nc\s+-l",
        r"ncat\s+-l",
        r"dd\s+if=",
        r":\(\)\{.*\}"
    ]

    def __init__(self, workspace: str = ".") -> None:
        self.workspace = os.path.abspath(workspace)

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return "执行 Shell 命令并返回输出结果"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 Shell 命令"
                }
            },
            "required": ["command"]
        }

    def _is_dangerous(self, command: str) -> str | None:
        """
        检测命令是否危险

        Returns:
            拦截信息或 None（放行）
        """
        for pattern in self.DENY_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return f"安全拦截：检测到危险命令模式 '{pattern}'"
        return None

    async def execute(self, command: str) -> str:
        """执行 Shell 命令"""
        # 检查工作目录是否存在
        if not os.path.exists(self.workspace):
            return f"错误：工作目录 '{self.workspace}' 不存在"

        # 检查命令是否包含危险操作
        if deny_msg := self._is_dangerous(command):
            return deny_msg

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=60
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return "命令执行超时（60秒），已终止"

            # 拼接输出
            output = stdout.decode("utf-8", errors="replace")
            if stderr:
                output += "\n标准错误:" + stderr.decode("utf-8", errors="replace")

            # 截断输出
            if len(output) > 10000:
                output = output[:10000] + "\n...(输出过长，已截断)"

            # 添加退出码
            output += f"\n[退出码: {process.returncode}]"

            return output

        except Exception as e:
            return f"命令执行失败：{str(e)}"