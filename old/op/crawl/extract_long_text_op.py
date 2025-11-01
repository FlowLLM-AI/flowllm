import asyncio

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.enumeration.role import Role
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall
from flowllm.utils.common_utils import get_datetime


@C.register_op(register_app="FlowLLM")
class ExtractLongTextOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(self, llm: str = "qwen3_80b_instruct", max_content_length: int = 30000, **kwargs):
        super().__init__(llm=llm, **kwargs)
        self.max_content_length = max_content_length

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": "Utilize the capabilities of LLM to parse content relevant to the query from long_text.",
                "input_schema": {
                    "long_text": {
                        "type": "string",
                        "description": "long_text",
                        "required": True,
                    },
                    "query": {
                        "type": "string",
                        "description": "query",
                        "required": True,
                    },
                },
            },
        )

    async def async_execute(self):
        long_text: str = self.input_dict["long_text"]
        long_text = long_text[: self.max_content_length]
        query: str = self.input_dict["query"]

        extract_content_prompt = self.prompt_format(
            prompt_name="extract_content_prompt",
            long_text=long_text,
            datetime=get_datetime(),
            query=query,
        )
        assistant_message = await self.llm.achat(messages=[Message(role=Role.USER, content=extract_content_prompt)])
        self.set_result(assistant_message.content)


async def main():
    from flowllm.app import FlowLLMApp

    async with FlowLLMApp(load_default_config=True):
        long_text = """..."""
        query = "紫金好不好"
        context = FlowContext(query=query, long_text=long_text)

        op = ExtractLongTextOp()
        await op.async_call(context=context)
        logger.info(op.output)


if __name__ == "__main__":
    asyncio.run(main())
