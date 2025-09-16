import asyncio
import json
from typing import List

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.enumeration.chunk_enum import ChunkEnum
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message, Role
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class StreamLLMOp(BaseAsyncToolOp):

    def __init__(self, llm: str = "qwen3_30b_thinking", save_answer: bool = True, **kwargs):
        super().__init__(llm=llm, save_answer=save_answer, **kwargs)

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "query_llm",
            "description": "use this query to query an LLM",
            "input_schema": {
                "query": {
                    "type": "string",
                    "description": "search keyword",
                    "required": False
                },
                "messages": {
                    "type": "array",
                    "description": "messages",
                    "required": False
                }
            }
        })

    async def async_execute(self):
        if self.input_dict.get("query"):
            query: str = self.input_dict.get("query")
            messages: List[Message] = [Message(role=Role.USER, content=query)]
        elif self.input_dict.get("messages"):
            messages: list = self.input_dict.get("messages")
            messages: List[Message] = [Message(**x) for x in messages]
        else:
            raise RuntimeError("query or messages is required")

        logger.info(f"messages={messages}")

        async for chunk, chunk_type in self.llm.astream_chat(messages):  # noqa
            if chunk_type in [ChunkEnum.ANSWER, ChunkEnum.THINK, ChunkEnum.ERROR]:
                await self.context.add_stream_chunk_and_type(chunk, chunk_type)
            elif chunk_type == ChunkEnum.TOOL:
                await self.context.add_stream_chunk_and_type(
                    chunk=json.dumps([x.model_dump() for x in chunk], ensure_ascii=False),
                    chunk_type=ChunkEnum.TOOL)

        await self.context.add_stream_done()


async def main():
    from flowllm.app import FlowLLMApp
    async with FlowLLMApp(load_default_config=True):

        context = FlowContext(query="what is ai?", stream_queue=asyncio.Queue())
        op = StreamLLMOp()
        task = asyncio.create_task(op.async_call(context=context))

        while True:
            stream_chunk = await context.stream_queue.get()
            if stream_chunk.done:
                print("\nend")
                break
            else:
                print(stream_chunk.chunk, end="")

        await task


if __name__ == "__main__":
    asyncio.run(main())
