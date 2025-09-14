import asyncio
from typing import List

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message, Role
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class SimpleLLMOp(BaseAsyncToolOp):

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
                    "required": True
                }
            },
            "output_schema": {
                "simple_llm_result": {
                    "type": "string",
                    "description": "simple llm result",
                }
            }
        })

    async def async_execute(self):
        query: str = self.input_dict["query"]
        logger.info(f"query={query}")
        messages: List[Message] = [Message(role=Role.USER, content=query)]
        assistant_message: Message = await self.llm.achat(messages)
        self.set_result(assistant_message.content)


async def main():
    from flowllm.app import FlowLLMApp
    async with FlowLLMApp(load_default_config=True):
        context = FlowContext(query="hello", stream_queue=asyncio.Queue())

        op = SimpleLLMOp()
        result = await op.async_call(context=context)
        print(op.output)
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
