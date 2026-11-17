"""系统信息查询工具模块"""

import platform
import sys

import psutil

from agent.tools.base import Tool


class SystemInfoTool(Tool):
    """系统信息查询工具

    返回当前操作系统的名称、Python 版本、CPU 核心数、内存总量等
    本机系统信息。该工具不需要任何参数。
    """

    @property
    def name(self) -> str:
        """工具名称"""
        return "system_info"

    @property
    def description(self) -> str:
        """工具功能描述"""
        return (
            "获取当前机器的系统信息，包括操作系统名称与版本、"
            "Python 版本、CPU 核心数、内存总量等。"
            "当用户询问本机硬件配置、系统环境或运行版本时使用。"
        )

    @property
    def parameters(self) -> dict:
        """工具参数定义（本工具无需参数）"""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    async def execute(self, **kwargs) -> str:
        """执行系统信息查询

        本工具不需要参数，kwargs 会被忽略。

        Returns:
            str: 格式化输出的系统信息
        """
        try:
            info = {
                "操作系统": self._os_info(),
                "机器架构": platform.machine(),
                "主机名": platform.node(),
                "Python 版本": sys.version.split()[0],
                "Python 实现": platform.python_implementation(),
                "CPU 核心数（逻辑）": psutil.cpu_count(logical=True),
                "CPU 核心数（物理）": psutil.cpu_count(logical=False),
                "内存总量": self._format_bytes(psutil.virtual_memory().total),
                "内存可用量": self._format_bytes(psutil.virtual_memory().available),
            }

            # 组装成多行文本
            lines = [f"{key}: {value}" for key, value in info.items()]
            return "\n".join(lines)

        except Exception as e:
            return f"获取系统信息失败：{str(e)}"

    def _os_info(self) -> str:
        """拼接操作系统名称与版本信息"""
        return (
            f"{platform.system()} "
            f"{platform.release()} "
            f"({platform.version()})"
        ).strip()

    def _format_bytes(self, size: int) -> str:
        """把字节数格式化成人类可读的单位（B/KB/MB/GB）"""
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"