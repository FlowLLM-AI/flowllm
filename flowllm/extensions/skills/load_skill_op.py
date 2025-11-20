"""Operation for loading a specific skill.

This module provides the LoadSkillOp class which loads the content of a
SKILL.md file from a specified skill directory. The skill directory is
looked up from the skill metadata dictionary using the skill name. If the
SKILL.md file contains YAML frontmatter, only the content after the
frontmatter is returned; otherwise, the full file content is returned.
"""

from pathlib import Path

from loguru import logger

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class LoadSkillOp(BaseAsyncToolOp):
    """Operation for loading a specific skill's instructions.

    This tool loads the content of a SKILL.md file for a given skill name.
    The skill directory is retrieved from the context's skill_metadata_dict,
    which should be populated by LoadSkillMetadataOp beforehand.

    The tool:
    1. Takes a skill_name as input
    2. Looks up the skill directory from skill_metadata_dict
    3. Reads the SKILL.md file from that directory
    4. If YAML frontmatter is present, returns only the content after it
    5. If no frontmatter is found, returns the full file content

    Returns:
        str: The skill instructions content. If the SKILL.md file has YAML
            frontmatter (delimited by "---"), returns only the content after
            the frontmatter. Otherwise, returns the complete file content.
            If the skill is not found, returns an error message string.

    Note:
        - The skill_name must exist in `self.context.skill_metadata_dict`
        - The SKILL.md file must exist in the skill directory
        - YAML frontmatter is detected by splitting on "---" delimiters
    """

    def build_tool_call(self) -> ToolCall:
        """Build the tool call definition for load_skill.

        Creates and returns a ToolCall object that defines the load_skill
        tool. This tool requires a skill_name parameter to identify which
        skill's instructions to load.

        Returns:
            ToolCall: A ToolCall object defining the load_skill tool with
                the following properties:
                - name: "load_skill"
                - description: Description of what the tool does
                - input_schema: A schema requiring a "skill_name" string
                    parameter that must be provided
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

        Loads the SKILL.md file content for the specified skill name. The
        method retrieves the skill directory from the context's skill metadata
        dictionary, reads the SKILL.md file, and extracts the instructions
        content (excluding YAML frontmatter if present).

        The method:
        1. Extracts the skill_name from input_dict
        2. Looks up the skill directory from skill_metadata_dict
        3. Constructs the path to SKILL.md file
        4. Checks if the file exists
        5. Reads the file content
        6. Splits content by "---" to detect YAML frontmatter
        7. Returns content after frontmatter if present, otherwise full content

        Returns:
            None: The result is set via `self.set_output()` with one of:
                - The skill instructions (content after YAML frontmatter)
                - The full file content (if no frontmatter is found)
                - An error message string (if skill file is not found)

        Raises:
            KeyError: If skill_name is not found in skill_metadata_dict.
                This should be handled by ensuring LoadSkillMetadataOp is
                called before LoadSkillOp.

        Note:
            - If the file has YAML frontmatter (format: "---\n...\n---\n..."),
              only the content after the second "---" is returned
            - If no frontmatter is detected, the entire file content is returned
            - File encoding is assumed to be UTF-8
        """
        # Extract skill name from input parameters
        skill_name = self.input_dict["skill_name"]
        # Look up the skill directory from the metadata dictionary
        # This dictionary should be populated by LoadSkillMetadataOp
        skill_dir = Path(self.context.skill_metadata_dict[skill_name]["skill_dir"])
        logger.info(f"🔧 Tool called: load_skill(skill_name='{skill_name}') with skill_dir={skill_dir}")

        # Construct the path to the SKILL.md file
        skill_path = skill_dir / "SKILL.md"

        # Check if the SKILL.md file exists
        if not skill_path.exists():
            content = f"❌ Skill '{skill_name}' not found"
            logger.exception(content)
            self.set_output(content)
            return

        # Read the SKILL.md file content
        content: str = skill_path.read_text(encoding="utf-8")
        self.set_output(content)

        logger.info(f"✅ Loaded skill: {skill_name} size={len(content)}")
