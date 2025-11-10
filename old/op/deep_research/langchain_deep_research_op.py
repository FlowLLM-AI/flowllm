import asyncio
import json
from typing import List, Dict

from loguru import logger

from flowllm.context import C, FlowContext
from flowllm.enumeration.chunk_enum import ChunkEnum
from flowllm.enumeration.role import Role
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall
from flowllm.utils.common_utils import get_datetime, extract_content


@C.register_op(register_app="FlowLLM")
class LangchainDeepResearchOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(
        self,
        llm: str = "qwen3_max_instruct",
        # llm: str = "qwen3_235b_instruct",
        # llm: str = "qwen3_80b_instruct",
        enable_research_brief: bool = True,
        max_concurrent_research_units: int = 3,
        max_researcher_iterations: int = 5,
        language: str = "zh",
        **kwargs,
    ):
        super().__init__(llm=llm, language=language, **kwargs)
        self.enable_research_brief: bool = enable_research_brief
        self.max_concurrent_research_units: int = max_concurrent_research_units
        self.max_researcher_iterations: int = max_researcher_iterations

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": "Conduct in-depth research on user query",
                "input_schema": {
                    "query": {
                        "type": "string",
                        "description": "user query",
                        "required": False,
                    },
                    "messages": {
                        "type": "array",
                        "description": "messages",
                        "required": False,
                    },
                },
            },
        )

    async def async_execute(self):
        await self.context.add_stream_chunk_and_type("开始深度研究", ChunkEnum.THINK)
        if self.input_dict.get("query"):
            query: str = self.input_dict.get("query")
            messages: List[Message] = [Message(role=Role.USER, content=query)]
        elif self.input_dict.get("messages"):
            messages: list = self.input_dict.get("messages")
            messages: List[Message] = [Message(**x) for x in messages]
        else:
            raise RuntimeError("query or messages is required")

        logger.info(f"messages={messages}")
        messages_merge = "\n".join([x.string_buffer for x in messages])
        if self.enable_research_brief:
            transform_research_topic_prompt = self.prompt_format(
                "transform_research_topic_prompt",
                messages=messages_merge,
                date=get_datetime(),
            )

            def parse_research_brief(message: Message):
                return extract_content(message.content)["research_brief"]

            research_brief = await self.llm.achat(
                messages=[Message(role=Role.USER, content=transform_research_topic_prompt)],
                callback_fn=parse_research_brief,
            )
        else:
            research_brief = "\n".join([x.string_buffer for x in messages])
        logger.info(f"research_brief={research_brief}")

        tool_dict: Dict[str, BaseAsyncToolOp] = {}
        for op in self.ops:
            assert isinstance(op, BaseAsyncToolOp)
            assert op.tool_call.name not in tool_dict, f"Duplicate tool name={op.tool_call.name}"
            tool_dict[op.tool_call.name] = op
            logger.info(f"add tool call={op.tool_call.simple_input_dump()}")

        lead_system_prompt = self.prompt_format(
            "lead_system_prompt",
            date=get_datetime(),
            max_researcher_iterations=self.max_researcher_iterations,
            max_concurrent_research_units=self.max_concurrent_research_units,
        )
        messages = [
            Message(role=Role.SYSTEM, content=lead_system_prompt),
            Message(role=Role.USER, content=research_brief),
        ]

        findings = []
        for i in range(self.max_researcher_iterations):
            assistant_message = await self.llm.achat(
                messages=messages,
                tools=[x.tool_call for x in tool_dict.values()],
            )
            messages.append(assistant_message)

            assistant_content = f"[{self.name}.{i}]"
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

            tool_calls_others = [x for x in assistant_message.tool_calls if x.name != "conduct_research"]
            tool_calls_conduct = [x for x in assistant_message.tool_calls if x.name == "conduct_research"]
            tool_calls_conduct = tool_calls_conduct[: self.max_concurrent_research_units]
            assistant_message.tool_calls = tool_calls_others + tool_calls_conduct

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
                messages.append(
                    Message(
                        role=Role.TOOL,
                        content=op.output,
                        tool_call_id=op.tool_call.id,
                    ),
                )
                tool_content = f"[{self.name}.{i}.{op.name}] {op.output[:200]}...\n\n"
                logger.info(tool_content)
                await self.context.add_stream_chunk_and_type(tool_content, ChunkEnum.TOOL)

                if op.tool_call.name == "conduct_research":
                    findings.append(op.output)

                if op.tool_call.name == "research_complete":
                    done = True

            if done:
                break

        logger.info(f"findings.size={len(findings)}")
        final_report_generation_prompt: str = self.prompt_format(
            "final_report_generation_prompt",
            research_brief=research_brief,
            messages=messages_merge,
            date=get_datetime(),
            findings="\n\n".join(findings),
        )
        report_generation_messages = [Message(role=Role.USER, content=final_report_generation_prompt)]

        async for chunk, chunk_type in self.llm.astream_chat(report_generation_messages):  # noqa
            if chunk_type in [ChunkEnum.ANSWER, ChunkEnum.THINK, ChunkEnum.ERROR]:
                await self.context.add_stream_chunk_and_type(str(chunk), chunk_type)


async def main():
    from flowllm.app import FlowLLMApp
    from flowllm.op.deep_research import ConductResearchOp
    from flowllm.op.search import DashscopeSearchOp
    from flowllm.op.gallery import ThinkToolOp
    from flowllm.op.gallery import ResearchCompleteOp

    async with FlowLLMApp(load_default_config=True):
        context = FlowContext(query="茅台公司未来业绩", stream_queue=asyncio.Queue())

        op = (
            LangchainDeepResearchOp()
            << (ConductResearchOp() << DashscopeSearchOp() << ThinkToolOp() << ResearchCompleteOp())
            << ThinkToolOp()
            << ResearchCompleteOp()
        )

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
