import asyncio
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

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "query_llm",
            "description": "use this query to query an LLM",
            "input_schema": {
                "query": {
                    "type": "string",
                    "description": "search keyword",
                    "required": True
                }
            }
        })

    async def async_execute(self):
        query: str = self.input_dict["query"]
        logger.info(f"query={query}")
        messages: List[Message] = [Message(role=Role.USER, content=query)]

        async for chunk, chunk_type in self.llm.astream_chat(messages):  # noqa
            if chunk_type == ChunkEnum.ANSWER:
                await self.context.add_stream_answer(chunk)

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
