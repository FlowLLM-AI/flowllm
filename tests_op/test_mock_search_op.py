"""Test script for MockSearchOp.

This script provides a simple test case for MockSearchOp class.
It can be run directly with: python test_mock_search_op.py
"""

import asyncio
import json

from flowllm.gallery.mock_search_op import MockSearchOp
from flowllm.main import FlowLLMApp


async def async_main():
    """Test function for MockSearchOp."""
    async with FlowLLMApp():
        # Single test: run mock search with a query and validate output
        print("=" * 80)
        print("Test: Running MockSearchOp with a query and validating JSON output")
        print("=" * 80)

        op = MockSearchOp()
        await op.async_call(query="latest AI research news")

        print("Output (raw):")
        print(op.context.response.answer)

        # Basic assertions
        assert op.context.response.answer is not None, "Output should not be None"
        assert isinstance(op.context.response.answer, str), "Output should be a string"
        assert len(op.context.response.answer) > 0, "Output should not be empty"

        # Validate it is valid JSON
        try:
            parsed = json.loads(op.context.response.answer)
            assert isinstance(parsed, (list, dict)), "Parsed JSON should be list or dict"
        except json.JSONDecodeError as e:
            raise AssertionError(f"Output should be valid JSON, got decode error: {e}") from e

        print("\n✓ Test passed\n")
        print("=" * 80)
        print("All tests passed!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(async_main())
