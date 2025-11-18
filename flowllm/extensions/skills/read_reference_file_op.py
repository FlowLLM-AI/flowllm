from loguru import logger
from pathlib import Path
from flowllm.context.service_context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class ReadReferenceFileOp(BaseAsyncToolOp):

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "read_reference_file",
            "description": "Read a reference file from a skill (e.g., forms.md, reference.md, ooxml.md)",
            "input_schema": {
                "skill_name": {
                    "type": "string",
                    "description": "skill name",
                    "required": False
                },
                "file_name": {
                    "type": "string",
                    "description": "reference file name",
                    "required": False
                },
                "path": {
                    "type": "string",
                    "description": "skills path",
                    "required": True
                }
            }
        })

    async def async_execute(self):
         
        if self.input_dict.get("skill_name"):
            skill_name = self.input_dict.get("skill_name")
        else:
            raise RuntimeError("skill_name is required")
        
        if self.input_dict.get("file_name"):
            file_name = self.input_dict.get("file_name")
        else:
            raise RuntimeError("reference_file_name is required")
        
        if self.input_dict.get("path"):
            skills_path = Path(self.input_dict.get("path"))
        else:
            raise RuntimeError("skills path is required")
          
        logger.info(f"🔧 Tool called: read_reference_file(skill_name='{skill_name}', file_name='{file_name}', path='{skills_path})")
        
        file_path = skills_path / skill_name / file_name
        if not file_path.exists():
            logger.exception(f"❌ File not found: {file_path}")
            self.set_result(f"File '{file_name}' not found in skill '{skill_name}'")
            return

        logger.info(f"✅ Read file: {skill_name}/{file_name}")
        self.set_result(file_path.read_text(encoding="utf-8"))


