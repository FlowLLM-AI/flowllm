"""Operation for loading a specific skill.

This module provides the LoadSkillOp class which loads the full content
of a SKILL.md file from a specified skill directory.
"""

from pathlib import Path

from loguru import logger

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class LoadSkillOp(BaseAsyncToolOp):
    """Operation for loading a specific skill's instructions.

    This tool loads the complete content of a SKILL.md file from a
    specified skill directory, including its YAML frontmatter and
    instructions.
    """

    def build_tool_call(self) -> ToolCall:
        """Build the tool call definition for load_skill.

        Returns:
            A ToolCall object defining the load_skill tool.
        """
        return ToolCall(
            **{
                "name": "load_skill",
                "description": "Load one skill's instructions from the SKILL.md.",
                "input_schema": {
                    "skill_name": {
                        "type": "string",
                        "description": "skill name",
                        "required": True,
                    },
                },
            },
        )

    async def async_execute(self):
        """Execute the load skill operation.

        Loads the SKILL.md file from the specified skill directory.
        If the skill is not found, sets an error message with available
        skills in the output.

        The file path is constructed as: {skill_dir}/{skill_name}/SKILL.md
        """
        skill_name = self.input_dict["skill_name"]
        skill_dir = Path(self.context.skill_dir)
        logger.info(f"🔧 Tool called: load_skill(skill_name='{skill_name}')")
        skill_path = skill_dir / skill_name / "SKILL.md"

        if not skill_path.exists():
            available = [d.name for d in skill_dir / skill_name.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
            logger.exception(f"❌ Skill '{skill_name}' not found")
            self.set_output(f"Skill '{skill_name}' not found. Available: {', '.join(available)}")
            return

        content = skill_path.read_text(encoding="utf-8")
        parts = content.split("---")
        if len(parts) < 3:
            logger.warning(f"No YAML frontmatter found in skill from {skill_path}")
            return

        logger.info(f"✅ Loaded skill: {skill_name}")
        self.set_output(content)
