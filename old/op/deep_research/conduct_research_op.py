import asyncio
import json
from typing import Dict, List

from loguru import logger

from flowllm.context import FlowContext, C
from flowllm.enumeration.chunk_enum import ChunkEnum
from flowllm.enumeration.role import Role
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.op.gallery.research_complete_op import ResearchCompleteOp
from flowllm.op.gallery.think_op import ThinkToolOp
from flowllm.op.search import DashscopeSearchOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall
from flowllm.utils.common_utils import get_datetime


@C.register_op(register_app="FlowLLM")
class ConductResearchOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(
        self,
        max_react_tool_calls: int = 5,
        max_content_len: int = 20000,
        save_answer: bool = False,
        llm: str = "qwen3_max_instruct",
        # llm: str = "qwen3_235b_instruct",
        # llm: str = "qwen3_80b_instruct",
        language: str = "zh",
        **kwargs,
    ):
        super().__init__(llm=llm, language=language, save_answer=save_answer, **kwargs)
        self.max_react_tool_calls: int = max_react_tool_calls
        self.max_content_len: int = max_content_len

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": "Conduct in-depth research on a single topic. If research on multiple topics is required, please invoke this tool multiple times.",
                "input_schema": {
                    "research_topic": {
                        "type": "string",
                        "description": "The topic to research. Should be a single topic, and should be described in high detail (at least a paragraph).",
                        "required": True,
                    },
                },
            },
        )

    async def async_execute(self):
        assert self.ops, "OpenResearchOp requires a search tool"
        logger.info(f"find {len(self.ops)} ops: {','.join([x.name for x in self.ops])}")

        search_op = self.ops[0]
        assert isinstance(search_op, BaseAsyncToolOp)
        research_system_prompt = self.prompt_format(
            prompt_name="research_system_prompt",
            date=get_datetime(),
            mcp_prompt="",
            search_tool=search_op.tool_call.name,
        )

        if self.input_dict.get("research_topic"):
            messages: List[Message] = [Message(role=Role.USER, content=self.input_dict.get("research_topic"))]
        elif self.input_dict.get("messages"):
            messages: List[Message] = [Message(**x) for x in self.input_dict.get("messages")]
        else:
            raise RuntimeError("research_topic or messages is required")

        logger.info(f"messages={messages}")

        messages = [Message(role=Role.SYSTEM, content=research_system_prompt)] + messages

        tool_dict: Dict[str, BaseAsyncToolOp] = {}
        for op in self.ops:
            assert isinstance(op, BaseAsyncToolOp)
            assert op.tool_call.name not in tool_dict, f"Duplicate tool name={op.tool_call.name}"
            tool_dict[op.tool_call.name] = op

        for i in range(self.max_react_tool_calls):
            assistant_message = await self.llm.achat(
                messages=messages,
                tools=[x.tool_call for x in tool_dict.values()],
            )
            messages.append(assistant_message)

            assistant_content = f"[{self.name}.{self.tool_index}.{i}]"
            if assistant_message.content:
                assistant_content += f" content={assistant_message.content}"
            if assistant_message.reasoning_content:
                assistant_content += f" reasoning={assistant_message.reasoning_content}"
            if assistant_message.tool_calls:
                tool_call_str = " | ".join(
                    [json.dumps(t.simple_output_dump(), ensure_ascii=False) for t in assistant_message.tool_calls]
                )
                assistant_content += f" tool_calls={tool_call_str}"
            assistant_content += "\n\n"
            logger.info(assistant_content)
            await self.context.add_stream_chunk_and_type(assistant_content, ChunkEnum.THINK)

            if not assistant_message.tool_calls:
                break

            ops: List[BaseAsyncToolOp] = []
            for tool in assistant_message.tool_calls:
                op = tool_dict[tool.name].copy()
                op.tool_call.id = tool.id
                ops.append(op)
                self.submit_async_task(op.async_call, **tool.argument_dict)

            await self.join_async_task()

            done: bool = False
            for op in ops:
                messages.append(
                    Message(
                        role=Role.TOOL,
                        content=op.output[: self.max_content_len],
                        tool_call_id=op.tool_call.id,
                    ),
                )
                tool_content = f"[{self.name}.{self.tool_index}.{i}.{op.name}] {op.output[:200]}...\n\n"
                logger.info(tool_content)
                await self.context.add_stream_chunk_and_type(tool_content, ChunkEnum.TOOL)
                if op.tool_call.name == "research_complete":
                    done = True

            if done:
                break

        messages = [x for x in messages if x.role != Role.SYSTEM]

        compress_system_prompt: str = self.prompt_format("compress_system_prompt", date=get_datetime())
        merge_messages = [
            Message(role=Role.SYSTEM, content=compress_system_prompt),
            *messages,
            Message(role=Role.USER, content=self.get_prompt("compress_user_prompt")),
        ]

        logger.info(f"merge_messages={merge_messages}")
        assistant_message = await self.llm.achat(messages=merge_messages)
        assistant_message.content = assistant_message.content[: self.max_content_len]
        chunk_type: ChunkEnum = ChunkEnum.ANSWER if self.save_answer else ChunkEnum.THINK
        content = f"{self.name}.{self.tool_index} content={assistant_message.content}"
        await self.context.add_stream_chunk_and_type(content, chunk_type)
        self.set_result(assistant_message.content)


async def main():
    from flowllm.app import FlowLLMApp

    async with FlowLLMApp(load_default_config=True):

        context = FlowContext(research_topic="茅台公司未来业绩", stream_queue=asyncio.Queue())
        op = ConductResearchOp() << DashscopeSearchOp() << ThinkToolOp() << ResearchCompleteOp()

        async def async_call():
            await op.async_call(context=context)
            await context.add_stream_done()

        task = asyncio.create_task(async_call())

        while True:
            stream_chunk = await context.stream_queue.get()
            if stream_chunk.done:
                print("\nend")
                await task
                break

            else:
                print(stream_chunk.chunk, end="")

        await task


if __name__ == "__main__":
    asyncio.run(main())
