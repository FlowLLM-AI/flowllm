"""Test script for WriteTodosOp.

This script provides test cases for WriteTodosOp class.
It can be run directly with: python test_write_todos_op.py
"""

import asyncio
import json

from flowllm.extension.file_tool import WriteTodosOp
from flowllm.main import FlowLLMApp


async def test_simple_input_schema():
    """Test case 1: Test tool_call.simple_input_dump()."""
    print("=" * 80)
    print("Test Case 1: Testing tool_call.simple_input_dump()")
    print("=" * 80)

    async with FlowLLMApp():
        op = WriteTodosOp()
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

        # Verify todos parameter structure
        todos_param = input_schema["function"]["parameters"]["properties"]["todos"]
        assert todos_param["type"] == "array"
        assert "items" in todos_param
        assert todos_param["items"]["type"] == "object"
        assert "properties" in todos_param["items"]
        assert "description" in todos_param["items"]["properties"]
        assert "status" in todos_param["items"]["properties"]
        assert "enum" in todos_param["items"]["properties"]["status"]

        print("\n✓ Test Case 1 passed: simple_input_dump() works correctly")
        print("=" * 80)


async def test_normal_async_execute():
    """Test case 2: Test normal async_execute."""
    print("\n" + "=" * 80)
    print("Test Case 2: Testing normal async_execute")
    print("=" * 80)

    async with FlowLLMApp():
        op = WriteTodosOp()

        # Test 1: Empty todo list
        print("\nTest 2.1: Empty todo list")
        await op.async_call(todos=[])
        print("\nOutput:")
        print(op.output)
        assert "cleared the todo list" in op.output.lower()

        # Test 2: Todo list with multiple items
        print("\nTest 2.2: Todo list with multiple items")
        todos = [
            {"description": "Task 1", "status": "pending"},
            {"description": "Task 2", "status": "in_progress"},
            {"description": "Task 3", "status": "completed"},
            {"description": "Task 4", "status": "cancelled"},
        ]
        await op.async_call(todos=todos)
        print("\nOutput:")
        print(op.output)
        assert "Successfully updated the todo list" in op.output
        assert "[pending] Task 1" in op.output
        assert "[in_progress] Task 2" in op.output
        assert "[completed] Task 3" in op.output
        assert "[cancelled] Task 4" in op.output

        print("\n✓ Test Case 2 passed: async_execute() works correctly")
        print("=" * 80)


async def test_exception_async_default_execute():
    """Test case 3: Test exception handling, executing async_default_execute."""
    print("\n" + "=" * 80)
    print("Test Case 3: Testing exception handling (async_default_execute)")
    print("=" * 80)

    async with FlowLLMApp():
        op = WriteTodosOp(raise_exception=False, max_retries=1)

        # Test: todos is not a list
        await op.async_call(todos="not a list")
        print("\nOutput after exception:")
        print(op.output)
        assert "Failed to update the todo list" in op.output

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
