"""Test script for StreamChatOp.

This script provides test cases for StreamChatOp class.
It can be run directly with: python test_stream_chat_op.py
"""

import asyncio

from flowllm.core.enumeration import Role, ChunkEnum
from flowllm.core.schema import Message
from flowllm.gallery.stream_chat_op import StreamChatOp
from flowllm.main import FlowLLMApp


async def async_task(op: StreamChatOp, messages, system_prompt: str, stream_queue: asyncio.Queue):
    """Wrapper function to call async_call and add done chunk."""
    await op.async_call(
        messages=messages,
        system_prompt=system_prompt,
        stream_queue=stream_queue,
    )
    await op.context.add_stream_done()


async def async_main():
    """Test function for StreamChatOp."""
    async with FlowLLMApp():
        # Test 1: Test basic streaming with ANSWER chunks
        print("=" * 80)
        print("Test 1: Testing basic streaming with ANSWER chunks")
        print("=" * 80)

        op = StreamChatOp()
        messages = [
            Message(role=Role.USER, content="Hello, how are you?"),
        ]

        stream_queue = asyncio.Queue()
        task = asyncio.create_task(
            async_task(
                op=op,
                messages=messages,
                system_prompt="You are a helpful assistant.",
                stream_queue=stream_queue,
            ),
        )

        # Collect stream chunks
        stream_chunks = []
        while True:
            stream_chunk = await stream_queue.get()
            if stream_chunk.done:
                print("\nend")
                break
            stream_chunks.append(stream_chunk)
            print(stream_chunk.chunk, end="", flush=True)

        await task

        assert len(stream_chunks) > 0, "Should receive at least one stream chunk"
        assert any(chunk.chunk_type == ChunkEnum.ANSWER for chunk in stream_chunks), "Should receive ANSWER chunks"
        print("\n✓ Test 1 passed\n")

        # Test 2: Test assertion error with invalid messages
        print("=" * 80)
        print("Test 2: Testing assertion error with invalid messages")
        print("=" * 80)

        op2 = StreamChatOp()
        try:
            await op2.async_call(
                messages=["not a Message object"],
                system_prompt="Test prompt",
                stream_queue=asyncio.Queue(),
            )
            print("✗ Test 2 failed: Should have raised an assertion error")
            assert False, "Should have raised AssertionError"
        except AssertionError as e:
            print(f"✓ Test 2 passed: Correctly raised AssertionError: {e}\n")

        print("=" * 80)
        print("All tests passed!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(async_main())
