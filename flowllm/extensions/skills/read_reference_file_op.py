"""Operation for reading reference files from skills.

This module provides the ReadReferenceFileOp class which allows reading
reference files (e.g., forms.md, reference.md) from skill directories.
"""

from pathlib import Path

from loguru import logger

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class ReadReferenceFileOp(BaseAsyncToolOp):
    """Operation for reading reference files from a skill directory.

    This tool allows reading reference files like forms.md, reference.md,
    or ooxml.md from a specific skill's directory.
    """

    def build_tool_call(self) -> ToolCall:
        """Build the tool call definition for read_reference_file.

        Returns:
            A ToolCall object defining the read_reference_file tool.
        """
        return ToolCall(
            **{
                "name": "read_reference_file",
                "description": "Read a reference file from a skill (e.g., forms.md, reference.md, ooxml.md)",
                "input_schema": {
                    "skill_name": {
                        "type": "string",
                        "description": "skill name",
                        "required": True,
                    },
                    "file_name": {
                        "type": "string",
                        "description": "reference file name or file path",
                        "required": True,
                    },
                },
            },
        )

    async def async_execute(self):
        """Execute the read reference file operation.

        Reads a reference file from the specified skill directory.
        If the file is not found, sets an error message in the output.

        The file path is constructed as: {skill_dir}/{skill_name}/{file_name}
        """
        skill_name = self.input_dict["skill_name"]
        file_name = self.input_dict["file_name"]
        skill_dir = Path(self.context.skill_dir)

        logger.info(f"🔧 Tool called: read_reference_file(skill_name='{skill_name}', file_name='{file_name}')")

        file_path = skill_dir / skill_name / file_name
        if not file_path.exists():
            logger.exception(f"❌ File not found: {file_path}")
            self.set_output(f"File '{file_name}' not found in skill '{skill_name}'")
            return

        logger.info(f"✅ Read file: {skill_name}/{file_name}")
        self.set_output(file_path.read_text(encoding="utf-8"))
