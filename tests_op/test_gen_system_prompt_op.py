"""Test script for GenSystemPromptOp.

This script provides test cases for GenSystemPromptOp class.
It can be run directly with: python test_gen_system_prompt_op.py
"""

import asyncio

from flowllm.core.enumeration import Role
from flowllm.core.schema import Message
from flowllm.core.utils import format_messages
from flowllm.gallery.gen_system_prompt_op import GenSystemPromptOp
from flowllm.main import FlowLLMApp


async def test_query_parameter():
    """Test with query parameter."""
    print("=" * 80)
    print("Test 1: Testing with query parameter")
    print("=" * 80)

    op = GenSystemPromptOp()
    await op.async_call(query="What is Python?")

    print(f"Query: {op.context.query}")
    print(f"System Prompt: {op.context.system_prompt}")
    print(f"System Prompt type: {type(op.context.system_prompt)}")
    assert op.context.system_prompt is not None, "System prompt should not be None"
    assert isinstance(op.context.system_prompt, str), "System prompt should be a string"
    assert len(op.context.system_prompt) > 0, "System prompt should not be empty"
    print("✓ Test 1 passed\n")


async def test_messages_parameter():
    """Test with messages parameter."""
    print("=" * 80)
    print("Test 2: Testing with messages parameter")
    print("=" * 80)

    op2 = GenSystemPromptOp()
    messages = [
        Message(role=Role.USER, content="I'm feeling frustrated with my code"),
        Message(role=Role.ASSISTANT, content="I understand. Let's work through this together."),
        Message(role=Role.USER, content="It keeps giving me errors"),
    ]
    await op2.async_call(messages=[msg.model_dump() for msg in messages])

    print(f"Messages count: {len(op2.context.messages)}")
    print(f"System Prompt: {op2.context.system_prompt}")
    assert op2.context.system_prompt is not None, "System prompt should not be None"
    assert isinstance(op2.context.system_prompt, str), "System prompt should be a string"
    assert len(op2.context.system_prompt) > 0, "System prompt should not be empty"
    print("✓ Test 2 passed\n")


async def test_format_messages():
    """Test format_messages utility function."""
    print("=" * 80)
    print("Test 3: Testing format_messages utility function")
    print("=" * 80)

    test_messages = [
        Message(role=Role.USER, content="Hello"),
        Message(role=Role.ASSISTANT, content="Hi there!"),
    ]
    formatted = format_messages(test_messages)
    print(f"Formatted messages:\n{formatted}")
    assert (
        "user: Hello".lower() in formatted.lower()
    ), f"Formatted messages should contain user message. formatted={formatted}"
    assert (
        "assistant: Hi there!".lower() in formatted.lower()
    ), f"Formatted messages should contain assistant message. formatted={formatted}"
    print("✓ Test 3 passed\n")


async def test_empty_input():
    """Test with empty query and empty messages (should raise assertion error)."""
    print("=" * 80)
    print("Test 4: Testing with empty query and empty messages (should raise assertion)")
    print("=" * 80)

    op4 = GenSystemPromptOp()
    try:
        await op4.async_call()
        print("✗ Test 4 failed: Should have raised an assertion error")
    except AssertionError as e:
        print(f"✓ Test 4 passed: Correctly raised AssertionError: {e}\n")


async def test_technical_query():
    """Test with technical query."""
    print("=" * 80)
    print("Test 5: Testing with technical query")
    print("=" * 80)

    op5 = GenSystemPromptOp()
    await op5.async_call(query="How do I implement a binary search tree in Python?")

    print(f"Query: {op5.context.query}")
    print(f"System Prompt: {op5.context.system_prompt}")
    assert op5.context.system_prompt is not None, "System prompt should not be None"
    assert len(op5.context.system_prompt) > 0, "System prompt should not be empty"
    print("✓ Test 5 passed\n")


async def async_main():
    """Test function for GenSystemPromptOp."""
    async with FlowLLMApp():
        await test_query_parameter()
        await test_messages_parameter()
        await test_format_messages()
        await test_empty_input()
        await test_technical_query()

        print("=" * 80)
        print("All tests passed!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(async_main())
