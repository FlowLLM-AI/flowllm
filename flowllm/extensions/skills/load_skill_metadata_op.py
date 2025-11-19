"""Operation for loading skill metadata.

This module provides the LoadSkillMetadataOp class which scans the skills
directory and extracts metadata (name and description) from all SKILL.md files.
"""

from pathlib import Path

from loguru import logger

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class LoadSkillMetadataOp(BaseAsyncToolOp):
    """Operation for loading metadata from all available skills.

    This tool scans the skills directory for SKILL.md files and extracts
    their metadata (name and description) from YAML frontmatter.
    Returns a JSON string containing a list of skill metadata.
    """

    def build_tool_call(self) -> ToolCall:
        """Build the tool call definition for load_skill_metadata.

        Returns:
            A ToolCall object defining the load_skill_metadata tool.
        """
        tool_params = {
            "name": "load_skill_metadata",
            "description": "Load metadata (name and description) for all available skills from the skills directory.",
            "input_schema": {},
        }
        return ToolCall(**tool_params)

    @staticmethod
    async def parse_skill_metadata(content: str, path: str) -> dict[str, str] | None:
        """Extract skill metadata (name and description) from SKILL.md content.

        Parses YAML frontmatter from SKILL.md files to extract the skill name
        and description. The frontmatter should be in the format:
        ---
        name: skill_name
        description: skill description
        ---

        Args:
            content: The content of the SKILL.md file.
            path: The file path (used for logging purposes).

        Returns:
            A dictionary with 'name' and 'description' keys, or None if
            parsing fails or required fields are missing.
        """
        parts = content.split("---")
        if len(parts) < 3:
            logger.warning(f"No YAML frontmatter found in skill from {path}")
            return None

        frontmatter_text = parts[1].strip()
        name = None
        description = None

        for line in frontmatter_text.split("\n"):
            line = line.strip()
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip("\"'")
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip("\"'")

        if not name or not description:
            logger.warning(f"Missing name or description in skill from {path}")
            return None

        return {
            "name": name,
            "description": description,
        }

    async def async_execute(self):
        """Execute the load skill metadata operation.

        Scans the skills directory recursively for all SKILL.md files,
        extracts their metadata, and returns a JSON string containing
        a list of all skill metadata entries.
        """
        skill_dir = Path(self.context.skill_dir)
        logger.info(f"🔧 Tool called: load_skill_metadata(path={skill_dir})")
        skill_files = list(skill_dir.rglob("SKILL.md"))

        skill_metadata_list = []
        for skill_file in skill_files:
            content = skill_file.read_text(encoding="utf-8")
            metadata = await self.parse_skill_metadata(content, str(skill_file))
            if metadata:
                skill_metadata_list.append(metadata)

        logger.info(f"✅ Loaded {len(skill_metadata_list)} skill metadata entries")

        # Return as JSON string for easy parsing
        skill_metadata_list = [f"- {x['name']}: {x['description']}" for x in skill_metadata_list]
        self.set_output("\n".join(skill_metadata_list))
