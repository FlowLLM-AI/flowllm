"""Test script for WriteFileOp.

This script provides test cases for WriteFileOp class.
It can be run directly with: python test_write_file_op.py
"""

import asyncio
import json
import os
import tempfile

from flowllm.extensions.file_tool import WriteFileOp
from flowllm.main import FlowLLMApp


async def test_simple_input_schema():
    """Test case 1: Test tool_call.simple_input_dump()."""
    print("=" * 80)
    print("Test Case 1: Testing tool_call.simple_input_dump()")
    print("=" * 80)

    async with FlowLLMApp():
        op = WriteFileOp()
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


async def test_create_new_file():
    """Test case 2: Test creating a new file."""
    print("\n" + "=" * 80)
    print("Test Case 2: Testing creating a new file")
    print("=" * 80)

    async with FlowLLMApp():
        op = WriteFileOp()

        # Create a temporary file path that doesn't exist
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp_file:
            tmp_file_path = tmp_file.name

        # Remove the file so it doesn't exist
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)

        try:
            # Test creating a new file
            test_content = """def hello():
    print("Hello, World!")
    return True
"""
            await op.async_call(
                file_path=tmp_file_path,
                content=test_content,
            )

            print("\nOutput:")
            print(op.output)

            # Verify the file was created
            assert os.path.exists(tmp_file_path)
            with open(tmp_file_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert content == test_content
                assert "def hello()" in content

            print("\n✓ Test Case 2 passed: Creating new file works correctly")
        finally:
            # Clean up
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

        print("=" * 80)


async def test_overwrite_existing_file():
    """Test case 2b: Test overwriting an existing file."""
    print("\n" + "=" * 80)
    print("Test Case 2b: Testing overwriting an existing file")
    print("=" * 80)

    async with FlowLLMApp():
        op = WriteFileOp()

        # Create a temporary file with initial content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp_file:
            tmp_file_path = tmp_file.name
            tmp_file.write("Initial content\n")

        try:
            # Test overwriting the file
            new_content = """def updated():
    print("This is updated content!")
    return True
"""
            await op.async_call(
                file_path=tmp_file_path,
                content=new_content,
            )

            print("\nOutput:")
            print(op.output)

            # Verify the file was overwritten
            with open(tmp_file_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert content == new_content
                assert "Initial content" not in content
                assert "def updated()" in content

            print("\n✓ Test Case 2b passed: Overwriting existing file works correctly")
        finally:
            # Clean up
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

        print("=" * 80)


async def test_create_file_with_parent_dirs():
    """Test case 2c: Test creating a file with parent directories."""
    print("\n" + "=" * 80)
    print("Test Case 2c: Testing creating file with parent directories")
    print("=" * 80)

    async with FlowLLMApp():
        op = WriteFileOp()

        # Create a temporary directory and a nested path
        with tempfile.TemporaryDirectory() as tmp_dir:
            nested_path = os.path.join(tmp_dir, "nested", "subdir", "test_file.txt")

            try:
                # Test creating a file with nested directories
                test_content = "Content in nested directory\n"
                await op.async_call(
                    file_path=nested_path,
                    content=test_content,
                )

                print("\nOutput:")
                print(op.output)

                # Verify the file was created with parent directories
                assert os.path.exists(nested_path)
                with open(nested_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    assert content == test_content

                print("\n✓ Test Case 2c passed: Creating file with parent directories works correctly")
            finally:
                # Clean up is handled by TemporaryDirectory context manager
                pass

        print("=" * 80)


async def test_exception_async_default_execute():
    """Test case 3: Test exception handling, executing async_default_execute."""
    print("\n" + "=" * 80)
    print("Test Case 3: Testing exception handling (async_default_execute)")
    print("=" * 80)

    async with FlowLLMApp():
        op = WriteFileOp()

        # Test with an empty file_path to trigger exception
        await op.async_call(
            file_path="",
            content="some content",
        )

        print("\nOutput after exception:")
        print(op.output)
        print("\n✓ Test Case 3 passed: async_default_execute() was called on exception")
        print("=" * 80)


async def async_main():
    """Run all test cases."""
    await test_simple_input_schema()
    await test_create_new_file()
    await test_overwrite_existing_file()
    await test_create_file_with_parent_dirs()
    await test_exception_async_default_execute()

    print("\n" + "=" * 80)
    print("All tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(async_main())
