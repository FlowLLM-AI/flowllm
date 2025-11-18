import re

from pathlib import Path
from loguru import logger
from flowllm.context.service_context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class LoadSkillOp(BaseAsyncToolOp):

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "load_skill",
            "description": "Load one skill's instructions from the SKILL.md.",
            "input_schema": {
                "skill_name": {
                    "type": "string",
                    "description": "skill name",
                    "required": True
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
    
        if self.input_dict.get("path"):
            skills_path = Path(self.input_dict.get("path"))
        else:
            raise RuntimeError("SKILL.md path is required")
        
        logger.info(f"🔧 Tool called: load_skill(skill_name='{skill_name}', path='{skills_path}')")
        
        skill_path = skills_path / skill_name / "SKILL.md"
        if not skill_path.exists():
            available = [d.name for d in skills_path.iterdir() # both files and folders at the top leve
                        if d.is_dir() and (d / "SKILL.md").exists()] # each Skill is stored in one folder 
            logger.exception(f"❌ Skill '{skill_name}' not found")
            self.set_result(f"Skill '{skill_name}' not found. Available: {', '.join(available)}")
            return

        content = skill_path.read_text(encoding="utf-8")
        frontmatter_match = re.match(
            r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL
        )
        
        logger.info(f"✅ Loaded skill: {skill_name}")
        if not frontmatter_match:
            self.set_result(content)
        else:
            self.set_result(frontmatter_match.group(2))

