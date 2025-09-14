import asyncio
import uuid
from typing import Optional

from flowllm.context.base_context import BaseContext
from flowllm.enumeration.chunk_enum import ChunkEnum
from flowllm.schema.flow_response import FlowResponse
from flowllm.schema.flow_stream_chunk import FlowStreamChunk


class FlowContext(BaseContext):

    def __init__(self,
                 flow_id: str = uuid.uuid4().hex,
                 response: Optional[FlowResponse] = None,
                 stream_queue: Optional[asyncio.Queue] = None,
                 **kwargs):
        super().__init__(**kwargs)

        self.flow_id: str = flow_id
        self.response: Optional[FlowResponse] = response if response is not None else FlowResponse()
        self.stream_queue: Optional[asyncio.Queue] = stream_queue

    async def add_stream_chunk(self, stream_chunk: FlowStreamChunk):
        stream_chunk.flow_id = self.flow_id
        await self.stream_queue.put(stream_chunk)
        return self

    async def add_stream_chunk_and_type(self, chunk: str | bytes, chunk_type: ChunkEnum):
        await self.stream_queue.put(FlowStreamChunk(flow_id=self.flow_id, chunk_type=chunk_type, chunk=chunk))
        return self

    async def add_stream_done(self):
        done_chunk = FlowStreamChunk(flow_id=self.flow_id, chunk_type=ChunkEnum.DONE, chunk="", done=True)
        await self.stream_queue.put(done_chunk)
        return self

    def add_response_error(self, e: Exception):
        self.response.success = False
        self.response.answer = str(e.args)

    def copy(self, **kwargs) -> "FlowContext":
        context_kwargs = self.dump()
        context_kwargs.update(kwargs)
        context_kwargs["response"] = FlowResponse()
        context = FlowContext(**context_kwargs)
        return context
