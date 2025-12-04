"""Test suite for OpenAICompatibleLLM.

This module provides comprehensive tests for OpenAICompatibleLLM including:
- Synchronous and asynchronous chat operations
- Streaming responses
- Tool calling functionality
- Error handling
- Different configurations

Requires proper environment variables:
- FLOW_LLM_API_KEY: API key for authentication
- FLOW_LLM_BASE_URL: Base URL for the API endpoint
"""

import asyncio

from flowllm.core.enumeration import Role
from flowllm.core.llm.openai_compatible_llm import OpenAICompatibleLLM
from flowllm.core.schema import Message, ToolCall
from flowllm.core.utils import load_env

load_env()

# Test model names
MODEL_NAME_1 = "qwen-max-2025-01-25"
MODEL_NAME_2 = "qwen3-30b-a3b-thinking-2507"


def create_llm():
    """Create a default OpenAICompatibleLLM instance for testing."""
    return OpenAICompatibleLLM(model_name=MODEL_NAME_1, temperature=0)


def create_llm_with_thinking():
    """Create an OpenAICompatibleLLM instance with thinking enabled."""
    return OpenAICompatibleLLM(model_name=MODEL_NAME_2, temperature=0)


def create_weather_tool():
    """Create a weather tool definition for testing."""
    return ToolCall(
        **{
            "type": "function",
            "function": {
                "name": "get_current_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        },
                        "unit": {
                            "type": "string",
                            "description": "The temperature unit, either 'celsius' or 'fahrenheit'",
                            "enum": ["celsius", "fahrenheit"],
                        },
                    },
                    "required": ["location"],
                },
            },
        },
    )


def create_calculator_tool():
    """Create a calculator tool definition for testing."""
    return ToolCall(
        **{
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "Perform basic arithmetic operations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "The operation to perform: add, subtract, multiply, or divide",
                            "enum": ["add", "subtract", "multiply", "divide"],
                        },
                        "a": {
                            "type": "number",
                            "description": "The first number",
                        },
                        "b": {
                            "type": "number",
                            "description": "The second number",
                        },
                    },
                    "required": ["operation", "a", "b"],
                },
            },
        },
    )


def test_chat_basic():
    """Test basic synchronous chat operation."""
    print("\n=== Test: chat_basic ===")
    llm = create_llm()
    message: Message = llm.chat(
        [Message(role=Role.USER, content="Hello!")],
        [],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    print(f"✓ Content: {message.content}")
    print(f"✓ Content length: {len(message.content)}")


def test_chat_with_thinking():
    """Test synchronous chat with thinking enabled."""
    print("\n=== Test: chat_with_thinking ===")
    llm = create_llm_with_thinking()
    message: Message = llm.chat(
        [Message(role=Role.USER, content="What is 2+2?")],
        [],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    print(f"✓ Content: {message.content}")
    print(f"✓ Reasoning content: {message.reasoning_content}")


def test_chat_with_tools():
    """Test synchronous chat with tool calling."""
    print("\n=== Test: chat_with_tools ===")
    llm = create_llm()
    weather_tool = create_weather_tool()
    message: Message = llm.chat(
        [Message(role=Role.USER, content="What's the weather in Beijing?")],
        [weather_tool],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    print(f"✓ Tool calls: {message.tool_calls}")
    print(f"✓ Tool calls count: {len(message.tool_calls)}")
    if message.tool_calls:
        print(f"✓ First tool call name: {message.tool_calls[0].name}")
        print(f"✓ First tool call arguments: {message.tool_calls[0].arguments}")


def test_chat_multiple_tools():
    """Test synchronous chat with multiple tools."""
    print("\n=== Test: chat_multiple_tools ===")
    llm = create_llm()
    weather_tool = create_weather_tool()
    calculator_tool = create_calculator_tool()
    message: Message = llm.chat(
        [Message(role=Role.USER, content="What's 10 + 20?")],
        [calculator_tool, weather_tool],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    print(f"✓ Tool calls: {message.tool_calls}")
    print(f"✓ Tool calls count: {len(message.tool_calls)}")
    if message.tool_calls:
        for i, tc in enumerate(message.tool_calls):
            print(f"✓ Tool call {i + 1}: name={tc.name}, arguments={tc.arguments}")


def test_chat_streaming():
    """Test synchronous chat with streaming enabled."""
    print("\n=== Test: chat_streaming ===")
    llm = create_llm()
    message: Message = llm.chat(
        [Message(role=Role.USER, content="Tell me a short story.")],
        [],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    print(f"✓ Content: {message.content}")
    print(f"✓ Content length: {len(message.content)}")


def test_chat_empty_message():
    """Test chat with empty message."""
    print("\n=== Test: chat_empty_message ===")
    llm = create_llm()
    message: Message = llm.chat(
        [Message(role=Role.USER, content="")],
        [],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")


def test_chat_long_conversation():
    """Test chat with a multi-turn conversation."""
    print("\n=== Test: chat_long_conversation ===")
    llm = create_llm()
    messages = [
        Message(role=Role.USER, content="My name is Alice."),
        Message(role=Role.ASSISTANT, content="Nice to meet you, Alice!"),
        Message(role=Role.USER, content="What's my name?"),
    ]
    message: Message = llm.chat(messages, [], enable_stream_print=False)
    print(f"✓ Message role: {message.role}")
    print(f"✓ Content: {message.content}")
    contains_alice = "Alice" in message.content or "alice" in message.content.lower()
    print(f"✓ Contains 'Alice': {contains_alice}")


async def test_achat_basic():
    """Test basic asynchronous chat operation."""
    print("\n=== Test: achat_basic ===")
    llm = create_llm()
    message: Message = await llm.achat(
        [Message(role=Role.USER, content="Hello!")],
        [],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    print(f"✓ Content: {message.content}")
    print(f"✓ Content length: {len(message.content)}")


async def test_achat_with_thinking():
    """Test asynchronous chat with thinking enabled."""
    print("\n=== Test: achat_with_thinking ===")
    llm = create_llm_with_thinking()
    message: Message = await llm.achat(
        [Message(role=Role.USER, content="What is 2+2?")],
        [],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    print(f"✓ Content: {message.content}")
    print(f"✓ Reasoning content: {message.reasoning_content}")


async def test_achat_with_tools():
    """Test asynchronous chat with tool calling."""
    print("\n=== Test: achat_with_tools ===")
    llm = create_llm()
    weather_tool = create_weather_tool()
    message: Message = await llm.achat(
        [Message(role=Role.USER, content="What's the weather in Beijing?")],
        [weather_tool],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    print(f"✓ Tool calls: {message.tool_calls}")
    print(f"✓ Tool calls count: {len(message.tool_calls)}")
    if message.tool_calls:
        for i, tc in enumerate(message.tool_calls):
            print(f"✓ Tool call {i + 1}: name={tc.name}, arguments={tc.arguments}")


async def test_achat_multiple_tools():
    """Test asynchronous chat with multiple tools."""
    print("\n=== Test: achat_multiple_tools ===")
    llm = create_llm()
    weather_tool = create_weather_tool()
    calculator_tool = create_calculator_tool()
    message: Message = await llm.achat(
        [Message(role=Role.USER, content="What's 10 * 20?")],
        [calculator_tool, weather_tool],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    print(f"✓ Tool calls: {message.tool_calls}")
    print(f"✓ Tool calls count: {len(message.tool_calls)}")
    if message.tool_calls:
        for i, tc in enumerate(message.tool_calls):
            print(f"✓ Tool call {i + 1}: name={tc.name}, arguments={tc.arguments}")


async def test_achat_streaming():
    """Test asynchronous chat with streaming."""
    print("\n=== Test: achat_streaming ===")
    llm = create_llm()
    message: Message = await llm.achat(
        [Message(role=Role.USER, content="Tell me a joke.")],
        [],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    print(f"✓ Content: {message.content}")


async def test_achat_long_conversation():
    """Test async chat with a multi-turn conversation."""
    print("\n=== Test: achat_long_conversation ===")
    llm = create_llm()
    messages = [
        Message(role=Role.USER, content="Count from 1 to 3."),
        Message(role=Role.ASSISTANT, content="1, 2, 3"),
        Message(role=Role.USER, content="What number comes after 3?"),
    ]
    message: Message = await llm.achat(messages, [], enable_stream_print=False)
    print(f"✓ Message role: {message.role}")
    print(f"✓ Content: {message.content}")
    contains_four = "4" in message.content or "four" in message.content.lower()
    print(f"✓ Contains '4' or 'four': {contains_four}")


def test_stream_chat_basic():
    """Test basic streaming chat with stream printing."""
    print("\n=== Test: stream_chat_basic ===")
    llm = create_llm()
    message: Message = llm.chat(
        [Message(role=Role.USER, content="Count to 5.")],
        [],
        enable_stream_print=True,
    )
    print(f"\n✓ Message role: {message.role}")
    print(f"✓ Content: {message.content}")
    print(f"✓ Content length: {len(message.content)}")


async def test_astream_chat_basic():
    """Test basic async streaming chat with stream printing."""
    print("\n=== Test: astream_chat_basic ===")
    llm = create_llm()
    message: Message = await llm.achat(
        [Message(role=Role.USER, content="Count to 3.")],
        [],
        enable_stream_print=True,
    )
    print(f"\n✓ Message role: {message.role}")
    print(f"✓ Content: {message.content}")
    print(f"✓ Content length: {len(message.content)}")


def test_stream_chat_with_tools():
    """Test streaming chat with tools and stream printing."""
    print("\n=== Test: stream_chat_with_tools ===")
    llm = create_llm()
    calculator_tool = create_calculator_tool()
    message: Message = llm.chat(
        [Message(role=Role.USER, content="Calculate 5 + 3")],
        [calculator_tool],
        enable_stream_print=True,
    )
    print(f"\n✓ Message role: {message.role}")
    print(f"✓ Tool calls: {message.tool_calls}")
    print(f"✓ Tool calls count: {len(message.tool_calls)}")
    if message.tool_calls:
        for i, tc in enumerate(message.tool_calls):
            print(f"✓ Tool call {i + 1}: name={tc.name}, arguments={tc.arguments}")


async def test_astream_chat_with_tools():
    """Test async streaming chat with tools and stream printing."""
    print("\n=== Test: astream_chat_with_tools ===")
    llm = create_llm()
    weather_tool = create_weather_tool()
    message: Message = await llm.achat(
        [Message(role=Role.USER, content="What's the weather in Shanghai?")],
        [weather_tool],
        enable_stream_print=True,
    )
    print(f"\n✓ Message role: {message.role}")
    print(f"✓ Tool calls: {message.tool_calls}")
    print(f"✓ Tool calls count: {len(message.tool_calls)}")
    if message.tool_calls:
        for i, tc in enumerate(message.tool_calls):
            print(f"✓ Tool call {i + 1}: name={tc.name}, arguments={tc.arguments}")


def test_custom_temperature():
    """Test LLM with custom temperature."""
    print("\n=== Test: custom_temperature ===")
    llm = OpenAICompatibleLLM(model_name=MODEL_NAME_1, temperature=0.5)
    message: Message = llm.chat(
        [Message(role=Role.USER, content="Hello!")],
        [],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")


def test_custom_seed():
    """Test LLM with custom seed."""
    print("\n=== Test: custom_seed ===")
    llm = OpenAICompatibleLLM(model_name=MODEL_NAME_1, seed=123)
    message: Message = llm.chat(
        [Message(role=Role.USER, content="Hello!")],
        [],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")


def test_custom_top_p():
    """Test LLM with custom top_p."""
    print("\n=== Test: custom_top_p ===")
    llm = OpenAICompatibleLLM(model_name=MODEL_NAME_1, top_p=0.9)
    message: Message = llm.chat(
        [Message(role=Role.USER, content="Hello!")],
        [],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")


def test_tool_call_weather():
    """Test tool calling with weather tool."""
    print("\n=== Test: tool_call_weather ===")
    llm = create_llm()
    weather_tool = create_weather_tool()
    message: Message = llm.chat(
        [Message(role=Role.USER, content="Get the weather for Beijing")],
        [weather_tool],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    if message.tool_calls:
        print(f"✓ Tool calls count: {len(message.tool_calls)}")
        tool_call = message.tool_calls[0]
        print(f"✓ Tool name: {tool_call.name}")
        has_location = "location" in tool_call.arguments.lower() or "beijing" in tool_call.arguments.lower()
        print(f"✓ Has location in arguments: {has_location}")


def test_tool_call_calculator():
    """Test tool calling with calculator tool."""
    print("\n=== Test: tool_call_calculator ===")
    llm = create_llm()
    calculator_tool = create_calculator_tool()
    message: Message = llm.chat(
        [Message(role=Role.USER, content="Calculate 25 multiplied by 4")],
        [calculator_tool],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    if message.tool_calls:
        print(f"✓ Tool calls count: {len(message.tool_calls)}")
        tool_call = message.tool_calls[0]
        print(f"✓ Tool name: {tool_call.name}")
        has_multiply = "multiply" in tool_call.arguments.lower() or "25" in tool_call.arguments
        print(f"✓ Has multiply/25 in arguments: {has_multiply}")


async def test_tool_call_async():
    """Test async tool calling."""
    print("\n=== Test: tool_call_async ===")
    llm = create_llm()
    weather_tool = create_weather_tool()
    message: Message = await llm.achat(
        [Message(role=Role.USER, content="What's the weather in Tokyo?")],
        [weather_tool],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    if message.tool_calls:
        print(f"✓ Tool calls count: {len(message.tool_calls)}")


def test_tool_call_multiple_tools_choice():
    """Test tool calling when multiple tools are available."""
    print("\n=== Test: tool_call_multiple_tools_choice ===")
    llm = create_llm()
    weather_tool = create_weather_tool()
    calculator_tool = create_calculator_tool()
    message: Message = llm.chat(
        [Message(role=Role.USER, content="What is 15 + 27?")],
        [calculator_tool, weather_tool],
        enable_stream_print=False,
    )
    print(f"✓ Message role: {message.role}")
    if message.tool_calls:
        tool_names = [tc.name for tc in message.tool_calls]
        print(f"✓ Tool names: {tool_names}")
        for i, tc in enumerate(message.tool_calls):
            print(f"✓ Tool call {i + 1}: name={tc.name}, arguments={tc.arguments}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Running OpenAICompatibleLLM Tests")
    print("=" * 60)

    # # Sync tests
    # test_chat_basic()
    # test_chat_with_thinking()
    # test_chat_with_tools()
    # test_chat_multiple_tools()
    # test_chat_streaming()
    # test_chat_empty_message()
    # test_chat_long_conversation()
    #
    # # Streaming tests
    # test_stream_chat_basic()
    # test_stream_chat_with_tools()
    #
    # # Configuration tests
    # test_custom_temperature()
    # test_custom_seed()
    # test_custom_top_p()
    #
    # # Tool calling tests
    # test_tool_call_weather()
    # test_tool_call_calculator()
    # test_tool_call_multiple_tools_choice()

    # Async tests
    print("\n" + "=" * 60)
    print("Running Async Tests")
    print("=" * 60)
    asyncio.run(test_achat_basic())
    asyncio.run(test_achat_with_thinking())
    asyncio.run(test_achat_with_tools())
    asyncio.run(test_achat_multiple_tools())
    asyncio.run(test_achat_streaming())
    asyncio.run(test_achat_long_conversation())
    asyncio.run(test_astream_chat_basic())
    asyncio.run(test_astream_chat_with_tools())
    asyncio.run(test_tool_call_async())

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
