"""Test script for EditOp.

This script provides test cases for EditOp class.
It can be run directly with: python test_edit_op.py
"""

import asyncio
import json
import tempfile
from pathlib import Path

from flowllm.extension.file_tool import EditOp
from flowllm.main import FlowLLMApp


async def test_simple_input_schema():
    """Test case 1: Test tool_call.simple_input_dump()."""
    print("=" * 80)
    print("Test Case 1: Testing tool_call.simple_input_dump()")
    print("=" * 80)

    async with FlowLLMApp():
        op = EditOp()
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
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            test_file = Path(f.name)
            f.write("Hello, world!\nThis is a test file.\nLine 3\n")

        try:
            op = EditOp()
            # Test replacing text
            await op.async_call(
                file_path=str(test_file),
                old_string="Hello, world!",
                new_string="Hello, Python!",
            )

            print("\nOutput:")
            print(op.output)

            # Verify the file was modified
            content = test_file.read_text(encoding="utf-8")
            assert "Hello, Python!" in content
            assert "Hello, world!" not in content

            print("\n✓ Test Case 2 passed: async_execute() works correctly")
            print("=" * 80)
        finally:
            # Clean up
            if test_file.exists():
                test_file.unlink()


async def test_exception_async_default_execute():
    """Test case 3: Test exception handling, executing async_default_execute."""
    print("\n" + "=" * 80)
    print("Test Case 3: Testing exception handling (async_default_execute)")
    print("=" * 80)

    async with FlowLLMApp():
        op = EditOp(raise_exception=False, max_retries=1)
        # Test with a non-existent file (should trigger exception)
        await op.async_call(
            file_path="/nonexistent/path/file.txt",
            old_string="test",
            new_string="test2",
        )

        print("\nOutput after exception:")
        print(op.output)

        # Verify that async_default_execute was called
        assert "Failed to edit file" in op.output

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
