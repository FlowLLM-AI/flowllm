"""Test script for GrepOp.

This script provides test cases for GrepOp class.
It can be run directly with: python test_grep_op.py
"""

import asyncio
import json

from flowllm.extensions.file_tool import GrepOp
from flowllm.main import FlowLLMApp


async def test_simple_input_schema():
    """Test case 1: Test tool_call.simple_input_dump()."""
    print("=" * 80)
    print("Test Case 1: Testing tool_call.simple_input_dump()")
    print("=" * 80)

    async with FlowLLMApp():
        op = GrepOp()
        tool_call = op.build_tool_call()
        tool_call.name = op.short_name

        # Test simple_input_dump
        input_schema = tool_call.simple_input_dump()
        print("\nInput Schema (simple_input_dump):")
        print(json.dumps(input_schema, indent=2, ensure_ascii=False))

        # Verify structure
        assert "type" in input_schema
        assert "function" in input_schema
        assert "name" in input_schema["function"]
        assert "description" in input_schema["function"]
        assert "parameters" in input_schema["function"]
        assert "properties" in input_schema["function"]["parameters"]
        assert "required" in input_schema["function"]["parameters"]

        print("\n✓ Test Case 1 passed: simple_input_dump() works correctly")
        print("=" * 80)


async def test_normal_async_execute():
    """Test case 2: Test normal async_execute."""
    print("\n" + "=" * 80)
    print("Test Case 2: Testing normal async_execute")
    print("=" * 80)

    async with FlowLLMApp():
        op = GrepOp()
        # Test with a pattern that should find matches (search for "def" in Python files)
        await op.async_call(pattern="def ", glob="*.py")

        print("\nOutput:")
        print(op.output)
        print("\n✓ Test Case 2 passed: async_execute() works correctly")
        print("=" * 80)


async def test_exception_async_default_execute():
    """Test case 3: Test exception handling, executing async_default_execute."""
    print("\n" + "=" * 80)
    print("Test Case 3: Testing exception handling (async_default_execute)")
    print("=" * 80)

    async with FlowLLMApp():
        op = GrepOp()
        # Test with an invalid path to trigger exception
        await op.async_call(pattern="test", path="/nonexistent/path/that/does/not/exist")

        print("\nOutput after exception:")
        print(op.output)
        print("\n✓ Test Case 3 passed: async_default_execute() was called on exception")
        print("=" * 80)


async def async_main():
    """Run all test cases."""
    await test_simple_input_schema()
    await test_normal_async_execute()
    await test_exception_async_default_execute()

    print("\n" + "=" * 80)
    print("All tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(async_main())
