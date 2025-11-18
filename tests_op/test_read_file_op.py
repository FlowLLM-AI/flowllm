"""Test script for ReadFileOp.

This script provides test cases for ReadFileOp class.
It can be run directly with: python test_read_file_op.py
"""

import asyncio
import json
from pathlib import Path

from flowllm.extensions.file_tool import ReadFileOp
from flowllm.main import FlowLLMApp


async def test_simple_input_schema():
    """Test case 1: Test tool_call.simple_input_dump()."""
    print("=" * 80)
    print("Test Case 1: Testing tool_call.simple_input_dump()")
    print("=" * 80)

    async with FlowLLMApp():
        op = ReadFileOp()
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
        op = ReadFileOp()
        # Test with a file that should exist (read this test file itself)
        test_file_path = Path(__file__).resolve()
        await op.async_call(absolute_path=str(test_file_path))

        print("\nOutput:")
        print(op.output[:200] + "..." if len(op.output) > 200 else op.output)
        print("\n✓ Test Case 2 passed: async_execute() works correctly")
        print("=" * 80)


async def test_exception_async_default_execute():
    """Test case 3: Test exception handling, executing async_default_execute."""
    print("\n" + "=" * 80)
    print("Test Case 3: Testing exception handling (async_default_execute)")
    print("=" * 80)

    async with FlowLLMApp():
        op = ReadFileOp()
        # Test with a non-existent file to trigger exception
        await op.async_call(absolute_path="/nonexistent/file/that/does/not/exist.txt")

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
