"""Test script for ToolCall.

This script provides test functions for ToolCall class serialization and deserialization.
It can be run directly with: python test_tool_call.py
"""

import json

from flowllm.core.schema.tool_call import ToolCall


def main():
    """Test function to demonstrate ToolCall serialization and deserialization."""
    data = {
        "id": "call_0fb6077ad56f4647b0b04a",
        "function": {
            "arguments": '{"symbol": "ZETA"}',
            "name": "get_stock_info",
        },
        "type": "function",
        "index": 0,
    }
    tool_call = ToolCall(**data)
    output_data = tool_call.simple_output_dump()
    assert output_data == data
    print(json.dumps(output_data, ensure_ascii=False))

    data = {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "It is very useful when you want to check the weather of a specified city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Cities or counties, such as Beijing, Hangzhou, Yuhang District, etc.",
                    },
                },
                "required": ["location"],
            },
        },
    }
    tool_call = ToolCall(**data)
    input_data = tool_call.simple_input_dump()
    assert input_data == data
    print(json.dumps(input_data, ensure_ascii=False))


if __name__ == "__main__":
    main()
