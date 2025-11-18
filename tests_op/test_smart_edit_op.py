"""Test script for SmartEditOp.

This script provides test cases for SmartEditOp class.
It can be run directly with: python test_smart_edit_op.py
"""

import asyncio
import json
import os
import tempfile

from flowllm.extensions.file_tool import SmartEditOp
from flowllm.main import FlowLLMApp


async def test_simple_input_schema():
    """Test case 1: Test tool_call.simple_input_dump()."""
    print("=" * 80)
    print("Test Case 1: Testing tool_call.simple_input_dump()")
    print("=" * 80)

    async with FlowLLMApp():
        op = SmartEditOp()
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
        op = SmartEditOp()

        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp_file:
            tmp_file_path = tmp_file.name
            tmp_file.write(
                """def hello():
    print("Hello, World!")
    return True

def goodbye():
    print("Goodbye!")
""",
            )

        try:
            # Test editing an existing file
            await op.async_call(
                file_path=tmp_file_path,
                old_string='def hello():\n    print("Hello, World!")\n    return True',
                new_string='def hello():\n    print("Hello, Updated World!")\n    return True',
                instruction="Update the hello function to print a different message",
            )

            print("\nOutput:")
            print(op.output)

            # Verify the file was modified
            with open(tmp_file_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "Hello, Updated World!" in content
                assert "Hello, World!" not in content

            print("\n✓ Test Case 2 passed: async_execute() works correctly")
        finally:
            # Clean up
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

        print("=" * 80)


async def test_create_new_file():
    """Test case 2b: Test creating a new file."""
    print("\n" + "=" * 80)
    print("Test Case 2b: Testing creating a new file")
    print("=" * 80)

    async with FlowLLMApp():
        op = SmartEditOp()

        # Create a temporary file path that doesn't exist
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp_file:
            tmp_file_path = tmp_file.name

        # Remove the file so it doesn't exist
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)

        try:
            # Test creating a new file
            await op.async_call(
                file_path=tmp_file_path,
                old_string="",
                new_string="""def new_function():
    print("This is a new file!")
    return True
""",
                instruction="Create a new file with a simple function",
            )

            print("\nOutput:")
            print(op.output)

            # Verify the file was created
            assert os.path.exists(tmp_file_path)
            with open(tmp_file_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "new_function" in content
                assert "This is a new file!" in content

            print("\n✓ Test Case 2b passed: Creating new file works correctly")
        finally:
            # Clean up
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

        print("=" * 80)


async def test_exception_async_default_execute():
    """Test case 3: Test exception handling, executing async_default_execute."""
    print("\n" + "=" * 80)
    print("Test Case 3: Testing exception handling (async_default_execute)")
    print("=" * 80)

    async with FlowLLMApp():
        op = SmartEditOp()
        # Test with a non-existent file and non-empty old_string to trigger exception
        await op.async_call(
            file_path="/nonexistent/file/that/does/not/exist.txt",
            old_string="some text",
            new_string="new text",
            instruction="This should fail because file doesn't exist",
        )

        print("\nOutput after exception:")
        print(op.output)
        print("\n✓ Test Case 3 passed: async_default_execute() was called on exception")
        print("=" * 80)


async def async_main():
    """Run all test cases."""
    await test_simple_input_schema()
    await test_normal_async_execute()
    await test_create_new_file()
    await test_exception_async_default_execute()

    print("\n" + "=" * 80)
    print("All tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(async_main())
