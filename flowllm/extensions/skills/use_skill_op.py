import asyncio
import json
import re
from pathlib import Path
from typing import List, Dict, Any

from loguru import logger

from flowllm.context import C, FlowContext
from flowllm.enumeration.chunk_enum import ChunkEnum
from flowllm.enumeration.role import Role
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class UseSkillOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(self,
                 llm: str = "qwen3_max_instruct",
                 # llm: str = "qwen3_235b_instruct",
                 # llm: str = "qwen3_80b_instruct",
                 max_iterations: int = 20,
                 **kwargs):
        super().__init__(llm=llm, **kwargs)
        self.max_iterations: int = max_iterations

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "description": "Automatically uses pre-built Skills relevant to the query when needed.",
            "input_schema": {
                "query": {
                    "type": "string",
                    "description": "query",
                    "required": True
                },
                "path": {
                    "type": "string",
                    "description": "skills path",
                    "required": True
                }
            }
        })

    async def get_skill_metadata(self, content: str, path: str) -> dict[str, Any] | None:
        frontmatter_match = re.match(
            r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL
        )

        if not frontmatter_match:
            logger.warning(f"No YAML frontmatter found in skill from {path}")
            return None

        frontmatter_text = frontmatter_match.group(1)
        name_match = re.search(r"^name:\s*(.+)$", frontmatter_text, re.MULTILINE)
        desc_match = re.search(r"^description:\s*(.+)$", frontmatter_text, re.MULTILINE)

        if not name_match or not desc_match:
            logger.warning(f"Missing name or description in skill from {path}")
            return None

        name = name_match.group(1).strip().strip("\"'")
        description = desc_match.group(1).strip().strip("\"'")

        return {
            "name": name,
            "description": description,
        }

    async def list_skills(self, path: Path) -> list[dict[str, Any]]:
        """
        Return the metadata for each Skill: its name and description.
        Agent loads this metadata at startup to know which Skills are available.
        
        This is the first level of progressive disclosure, 
        where Agent identifies the available Skills without loading their entire instructions.
        """
        skill_files = list(path.rglob("SKILL.md"))

        skill_metadatas = ""
        for skill_file in skill_files:
            content = skill_file.read_text(encoding="utf-8")
            metadata = await self.get_skill_metadata(content, str(skill_file))
            skill_metadatas += f"- {metadata["name"]}: {metadata["description"]}\n"
        
        return skill_metadatas

    async def async_execute(self):
        
        if self.input_dict.get("query"):
            query = self.input_dict.get("query")
        else:
            raise RuntimeError("query is required")
    
        if self.input_dict.get("path"):
            skill_path = Path(self.input_dict.get("path"))
        else:
            raise RuntimeError("query is required")

        logger.info(f"UseSkillOp processing query: {query} with access to skills in {skill_path}")

        tool_dict: Dict[str, BaseAsyncToolOp] = {}
        for op in self.ops:
            assert isinstance(op, BaseAsyncToolOp)
            assert op.tool_call.name not in tool_dict, f"Duplicate tool name={op.tool_call.name}"
            tool_dict[op.tool_call.name] = op
            logger.info(f"add tool call={op.tool_call.simple_input_dump()}")

        # load the skill metadatas at startup and include them in the system prompt
        skill_metadatas = await self.list_skills(skill_path)
        system_prompt = self.prompt_format("system_prompt",
                                        skills_path=skill_path,
                                        skill_metadatas=skill_metadatas)
        # logger.info(system_prompt)
        messages = [
            Message(role=Role.SYSTEM, content=system_prompt),
            Message(role=Role.USER, content=query),
        ]

        results = []
        for i in range(self.max_iterations):
            assistant_message = await self.llm.achat(messages=messages,
                                                     tools=[x.tool_call for x in tool_dict.values()])
            messages.append(assistant_message)

            assistant_content = f"[{self.name}.{i}]"
            if assistant_message.content:
                assistant_content += f" content={assistant_message.content}"
            if assistant_message.reasoning_content:
                assistant_content += f" reasoning={assistant_message.reasoning_content}"
            if assistant_message.tool_calls:
                tool_call_str = " | ".join([json.dumps(t.simple_output_dump(), ensure_ascii=False) \
                                            for t in assistant_message.tool_calls])
                assistant_content += f" tool_calls={tool_call_str}"
            assistant_content += "\n\n"
            logger.info(assistant_content)
            await self.context.add_stream_chunk_and_type(assistant_content, ChunkEnum.THINK)

            if not assistant_message.tool_calls:
                break

            ops: List[BaseAsyncToolOp] = []
            for j, tool in enumerate(assistant_message.tool_calls):
                op = tool_dict[tool.name].copy()
                op.tool_call.id = tool.id
                ops.append(op)
                logger.info(f"{self.name} submit op{j}={op.name} argument={tool.argument_dict}")
                self.submit_async_task(op.async_call, **tool.argument_dict, stream_queue=self.context.stream_queue)

            await self.join_async_task()

            done: bool = False
            for op in ops:
                messages.append(Message(role=Role.TOOL,
                                        content=op.output,
                                        tool_call_id=op.tool_call.id))
                tool_content = f"[{self.name}.{i}.{op.name}] {op.output[:200]}...\n\n"
                logger.info(tool_content)
                await self.context.add_stream_chunk_and_type(tool_content, ChunkEnum.TOOL)

                if op.tool_call.name == "task_complete":
                    done = True

            if done:
                break


async def main():
    from flowllm.app import FlowLLMApp
    from flowllm.op.skills import LoadSkillOp, ReadReferenceFileOp, RunShellCommandOp, TaskCompleteOp

    async with FlowLLMApp(load_default_config=True):
        #  Help me merge two PDF files (minimal-document.pdf and pdflatex-outline) and save to merged.pdf
        context = FlowContext(query="Fill Sample-Fillable-PDF.pdf with: name='Alice Johnson', select first choice from dropdown, check options 1 and 3, dependent name='Bob Johnson', age='12'. Save as filled-sample.pdf", 
                              path="./skills",
                              stream_queue=asyncio.Queue())

        op = UseSkillOp() \
             << LoadSkillOp() << ReadReferenceFileOp() << RunShellCommandOp() << TaskCompleteOp()

        await op.async_call(context=context)
        
        # async def async_call():
        #     await op.async_call(context=context)
        #     await context.add_stream_done()

        # task = asyncio.create_task(async_call())

        # while True:
        #     stream_chunk = await context.stream_queue.get()
        #     if stream_chunk.done:
        #         print("\nend")
        #         await task
        #         break

        #     else:
        #         print(stream_chunk.chunk, end="")

        # await task


if __name__ == "__main__":
    asyncio.run(main())
