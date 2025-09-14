import asyncio
import json
from typing import List

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.enumeration.chunk_enum import ChunkEnum
from flowllm.op import BaseToolOp
from flowllm.schema.message import Message, Role
from flowllm.schema.tool_call import ToolCall


@C.register_op(name="stream_llm_op")
class StreamLLMOp(BaseToolOp):

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
            if chunk_type == ChunkEnum.ANSWER:
                await self.context.add_stream_answer(chunk)
            elif chunk_type == ChunkEnum.THINK:
                await self.context.add_stream_think(chunk)
            elif chunk_type == ChunkEnum.ERROR:
                await self.context.add_stream_error(chunk)
            elif chunk_type == ChunkEnum.TOOL:
                await self.context.add_stream_tool(json.dumps([x.model_dump() for x in chunk], ensure_ascii=False))

        await self.context.add_stream_done()


async def main():
    C.set_service_config().init_by_service_config()
    context = FlowContext(query="hello, introduce yourself.", stream_queue=asyncio.Queue())

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
