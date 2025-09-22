from typing import List

from loguru import logger

from flowllm.context import C
from flowllm.enumeration.chunk_enum import ChunkEnum
from flowllm.enumeration.role import Role
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall
from flowllm.utils.common_utils import get_datetime


@C.register_op(register_app="FlowLLM")
class OpenCompressOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(self, llm: str = "qwen3_80b_instruct", return_answer: bool = False, **kwargs):
        super().__init__(llm=llm, **kwargs)
        self.return_answer: bool = return_answer

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "description": "compress messages",
            "input_schema": {
                "messages": {
                    "type": "array",
                    "description": "messages",
                    "required": True
                }
            }
        })

    async def async_execute(self):
        messages: List[Message] = self.input_dict["messages"]
        messages = [Message(**m) if isinstance(m, dict) else m for m in messages]

        compress_system_prompt: str = self.prompt_format("compress_system_prompt", date=get_datetime())
        messages = [
            Message(role=Role.SYSTEM, content=compress_system_prompt),
            *messages,
            Message(role=Role.USER, content=self.get_prompt("compress_user_prompt"))
        ]

        logger.info(f"messages={messages}")
        assistant_message = await self.llm.achat(messages=messages)
        chunk_type: ChunkEnum = ChunkEnum.ANSWER if self.return_answer else ChunkEnum.THINK
        await self.context.add_stream_chunk_and_type(assistant_message.content, chunk_type)
        self.set_result(assistant_message.content)



