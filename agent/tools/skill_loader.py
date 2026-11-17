"""技能加载工具模块"""

import os

from agent.tools.base import Tool


class LoadSkillTool(Tool):
    """
    技能加载工具。

    按名称读取 skills/ 目录下的 SKILL.md 技能定义并返回内容。
    技能是一份指导 Agent 如何完成某类任务的说明文档，
    Agent 加载后按其中的步骤使用已有工具完成任务。
    """

    def __init__(self, skills_dir: str):
        """
        初始化 LoadSkillTool。

        Args:
            skills_dir: 技能目录的绝对路径（如 <workspace>/skills）
        """
        self.skills_dir = os.path.abspath(skills_dir)

    @property
    def name(self) -> str:
        return "load_skill"

    @property
    def description(self) -> str:
        available = self._list_skills()
        skills_str = ", ".join(available) if available else "（暂无）"
        return (
            "加载一个技能（skill）。技能是一份指导你如何完成某类任务的说明文档，"
            "例如数据分析、代码审查、写作等。"
            f"当前可用技能：{skills_str}。"
            "当你需要执行与某个技能匹配的任务时，先调用本工具加载技能内容，"
            "再按照技能中的步骤执行。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "技能名称，例如 csv-data-analysis"
                }
            },
            "required": ["skill_name"]
        }

    async def execute(self, **kwargs) -> str:
        """
        执行技能加载。

        Args:
            skill_name: 技能名称（对应 skills/<技能名>/SKILL.md）。

        Returns:
            str: 技能文档内容，或错误信息。
        """
        skill_name = kwargs.get("skill_name", "")
        if not skill_name or not isinstance(skill_name, str):
            return "错误：必须提供 skill_name 参数"

        # 防止路径穿越（技能名只允许简单名称）
        if "/" in skill_name or "\\" in skill_name or ".." in skill_name:
            return f"错误：非法技能名称 - {skill_name}"

        skill_path = os.path.join(self.skills_dir, skill_name, "SKILL.md")
        if not os.path.isfile(skill_path):
            available = self._list_skills()
            hint = f"。可用技能：{', '.join(available) if available else '（无）'}"
            return f"错误：技能 '{skill_name}' 不存在{hint}"

        try:
            with open(skill_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"错误：读取技能失败 - {str(e)}"

    def _list_skills(self) -> list[str]:
        """列出 skills 目录下所有技能名称（存在 SKILL.md 的子目录）"""
        if not os.path.isdir(self.skills_dir):
            return []
        return sorted(
            name
            for name in os.listdir(self.skills_dir)
            if os.path.isfile(os.path.join(self.skills_dir, name, "SKILL.md"))
        )
