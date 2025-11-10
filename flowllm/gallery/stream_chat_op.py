"""Stream chat operation for flowllm.

This module provides an async operation that streams chat responses from an LLM,
handling different chunk types including answers, thinking content, errors, and tool calls.
"""

from loguru import logger

from ..core.context import C
from ..core.enumeration import Role, ChunkEnum
from ..core.op import BaseAsyncOp
from ..core.schema import Message, FlowStreamChunk


@C.register_op()
class StreamChatOp(BaseAsyncOp):
    """Async operation for streaming chat responses from an LLM.

    This operation processes messages and streams responses chunk by chunk,
    handling different types of content including regular answers, reasoning
    content, tool calls, and errors. It adds system prompts and processes
    streaming chunks from the LLM.
    """

    file_path: str = __file__

    def __init__(
        self,
        llm: str = "qwen3_30b_instruct",
        **kwargs,
    ):
        super().__init__(llm=llm, **kwargs)

    async def async_execute(self):
        messages = self.context.messages
        assert isinstance(messages, list) and all(
            isinstance(m, Message) for m in messages
        ), "`messages` must be a list of Message objects!"

        system_prompt = self.context.system_prompt
        assert system_prompt, "`system_prompt` is required!"

        messages = [Message(role=Role.SYSTEM, content=system_prompt)] + messages
        logger.info(f"messages={messages}")

        async for stream_chunk in self.llm.astream_chat(messages):
            assert isinstance(stream_chunk, FlowStreamChunk)
            if stream_chunk.chunk_type in [ChunkEnum.ANSWER, ChunkEnum.THINK, ChunkEnum.ERROR, ChunkEnum.TOOL]:
                await self.context.add_stream_chunk(stream_chunk)
