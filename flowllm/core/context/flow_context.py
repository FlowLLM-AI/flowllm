"""Flow context for managing flow execution state.

This module provides a context class for managing the state of flow execution,
including flow identification, response handling, and streaming capabilities.
"""

import asyncio
import uuid
from typing import Optional

from .base_context import BaseContext
from ..enumeration import ChunkEnum
from ..schema import FlowResponse
from ..schema import FlowStreamChunk


class FlowContext(BaseContext):
    """Context for managing flow execution state and streaming.

    This class manages the state of a single flow execution, including:
    - Flow identification
    - Response handling
    - Stream queue for asynchronous streaming

    Attributes:
        flow_id: Unique identifier for the flow instance.
        response: FlowResponse object for storing flow results.
        stream_queue: Asynchronous queue for streaming chunks.
    """

    def __init__(
        self,
        flow_id: str = uuid.uuid4().hex,
        response: Optional[FlowResponse] = None,
        stream_queue: Optional[asyncio.Queue] = None,
        **kwargs,
    ):
        """Initialize FlowContext with flow ID and optional components.

        Args:
            flow_id: Unique identifier for the flow instance.
                Defaults to a random UUID hex string.
            response: FlowResponse object. If None, a new FlowResponse
                will be created.
            stream_queue: Asynchronous queue for streaming chunks.
            **kwargs: Additional context data to store.
        """
        super().__init__(**kwargs)

        self.flow_id: str = flow_id
        self.response: Optional[FlowResponse] = response if response is not None else FlowResponse()
        self.stream_queue: Optional[asyncio.Queue] = stream_queue

    async def add_stream_chunk(self, stream_chunk: FlowStreamChunk):
        """Add a stream chunk to the stream queue.

        Args:
            stream_chunk: The stream chunk to add.

        Returns:
            Self for method chaining.
        """
        stream_chunk.flow_id = self.flow_id
        await self.stream_queue.put(stream_chunk)
        return self

    async def add_stream_done(self):
        """Add a done signal to the stream queue.

        Returns:
            Self for method chaining.
        """
        done_chunk = FlowStreamChunk(flow_id=self.flow_id, chunk_type=ChunkEnum.DONE, chunk="", done=True)
        await self.stream_queue.put(done_chunk)
        return self

    def add_response_error(self, e: Exception):
        """Add an error to the flow response.

        Args:
            e: The exception to record as an error.
        """
        self.response.success = False
        self.response.answer = str(e.args)

    # def copy(self, **kwargs) -> "FlowContext":
    #     """Create a copy of the flow context with optional updates.
    #
    #     Args:
    #         **kwargs: Additional context data to update in the copy.
    #
    #     Returns:
    #         A new FlowContext instance with copied data.
    #     """
    #     context_kwargs = self.dump()
    #     context_kwargs.update(kwargs)
    #     context_kwargs["response"] = FlowResponse()
    #     context = FlowContext(**context_kwargs)
    #     return context
