"""Unit tests for stream utility helpers."""

import asyncio
import json

import pytest

from flowllm.enumeration import ChunkEnum
from flowllm.schema import StreamChunk
from flowllm.utils.common_utils import _format_chunk, execute_stream_task


def test_format_chunk_supports_str_bytes_chunk_and_done_marker():
    """Chunks are rendered correctly for all transport formats."""
    chunk = StreamChunk(chunk_type=ChunkEnum.CONTENT, chunk="hello")

    as_str = _format_chunk(chunk, "str")
    assert isinstance(as_str, str)
    assert as_str.startswith("data:")
    assert json.loads(as_str.removeprefix("data:").strip())["chunk"] == "hello"

    assert _format_chunk(chunk, "bytes") == as_str.encode()
    assert _format_chunk(chunk, "chunk") is chunk
    assert _format_chunk(StreamChunk(done=True), "str") == "data:[DONE]\n\n"


def test_execute_stream_task_flushes_remaining_chunks_after_task_finishes():
    """A completed producer still lets queued chunks drain before DONE."""

    async def run():
        queue: asyncio.Queue[StreamChunk] = asyncio.Queue()
        await queue.put(StreamChunk(chunk="one"))
        await queue.put(StreamChunk(chunk="two"))

        async def producer():
            return None

        task = asyncio.create_task(producer())
        items = [item async for item in execute_stream_task(queue, task, output_format="chunk")]

        assert [item.chunk for item in items] == ["one", "two", ""]
        assert items[-1].done is True
        assert items[-1].chunk_type == ChunkEnum.DONE

    asyncio.run(run())


def test_execute_stream_task_raises_task_exception():
    """Producer exceptions are surfaced to callers."""

    async def run():
        queue: asyncio.Queue[StreamChunk] = asyncio.Queue()

        async def producer():
            raise RuntimeError("boom")

        task = asyncio.create_task(producer())
        with pytest.raises(RuntimeError, match="boom"):
            _ = [item async for item in execute_stream_task(queue, task, task_name="job")]

    asyncio.run(run())
