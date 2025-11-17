"""Test script for TokenCountOp.

This script provides a simple test case for TokenCountOp class.
It can be run directly with: python test_token_count_op.py
"""

import asyncio

from flowllm.gallery import TokenCountOp
from flowllm.main import FlowLLMApp


async def async_main():
    """Test function for TokenCountOp."""
    async with FlowLLMApp():
        print("=" * 80)
        print("Test: Running TokenCountOp with sample messages")
        print("=" * 80)

        op = TokenCountOp()

        # Prepare messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well, thank you for asking!"},
        ]

        print("Messages to count:")
        for msg in messages:
            print(f"  - {msg['role']}: {msg['content']}")
        print()

        # Execute the operation
        await op.async_call(messages=messages)

        print("\n✓ Test completed successfully")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(async_main())
