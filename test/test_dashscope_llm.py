"""
Test module for DashscopeLLM implementation.

This module contains unit tests for the DashscopeLLM class,
testing initialization, message conversion, and basic functionality.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from flowllm.llm.dashscope_llm import DashscopeLLM
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall
from flowllm.enumeration.role import Role


class TestDashscopeLLM:
    """Test cases for DashscopeLLM class"""

    def test_initialization(self):
        """Test DashscopeLLM initialization with default parameters"""
        llm = DashscopeLLM(model_name="qwen-plus-2025-04-28")
        
        assert llm.model_name == "qwen-plus-2025-04-28"
        assert llm.temperature == 0.0000001
        assert llm.enable_search is False
        assert llm.enable_thinking is False
        assert llm.max_retries == 5

    def test_initialization_with_custom_params(self):
        """Test DashscopeLLM initialization with custom parameters"""
        llm = DashscopeLLM(
            model_name="qwq-plus-latest",
            temperature=0.7,
            enable_search=True,
            enable_thinking=True,
            max_retries=3
        )
        
        assert llm.model_name == "qwq-plus-latest"
        assert llm.temperature == 0.7
        assert llm.enable_search is True
        assert llm.enable_thinking is True
        assert llm.max_retries == 3

    def test_convert_messages_to_dashscope(self):
        """Test message conversion to Dashscope format"""
        llm = DashscopeLLM(model_name="qwen-plus-2025-04-28")
        
        messages = [
            Message(role=Role.USER, content="Hello"),
            Message(role=Role.ASSISTANT, content="Hi there!"),
            Message(role=Role.USER, reasoning_content="Think about this", content="")
        ]
        
        dashscope_messages = llm._convert_messages_to_dashscope(messages)
        
        assert len(dashscope_messages) == 3
        assert dashscope_messages[0].role == "user"
        assert dashscope_messages[0].content == "Hello"
        assert dashscope_messages[1].role == "assistant"
        assert dashscope_messages[1].content == "Hi there!"
        # Should use reasoning_content when content is empty
        assert dashscope_messages[2].content == "Think about this"

    def test_convert_tools_to_dashscope(self):
        """Test tool conversion to Dashscope format"""
        llm = DashscopeLLM(model_name="qwen-plus-2025-04-28")
        
        tools = [
            ToolCall(
                name="search_web",
                description="Search the web for information",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            )
        ]
        
        dashscope_tools = llm._convert_tools_to_dashscope(tools)
        
        assert len(dashscope_tools) == 1
        assert dashscope_tools[0]["type"] == "function"
        assert dashscope_tools[0]["function"]["name"] == "search_web"
        assert dashscope_tools[0]["function"]["description"] == "Search the web for information"
        assert "query" in dashscope_tools[0]["function"]["parameters"]["properties"]

    def test_convert_tools_to_dashscope_empty(self):
        """Test tool conversion with empty tool list"""
        llm = DashscopeLLM(model_name="qwen-plus-2025-04-28")
        
        dashscope_tools = llm._convert_tools_to_dashscope([])
        assert dashscope_tools is None
        
        dashscope_tools = llm._convert_tools_to_dashscope(None)
        assert dashscope_tools is None

    @patch.dict(os.environ, {'DASHSCOPE_API_KEY': 'test_key'})
    def test_api_key_from_env(self):
        """Test API key loading from environment variable"""
        llm = DashscopeLLM(model_name="qwen-plus-2025-04-28")
        assert llm.api_key == "test_key"

    def test_model_name_validation(self):
        """Test model name validation with supported models"""
        supported_models = [
            "qwen-plus-2025-04-28",
            "qwq-plus-latest", 
            "qwen-max-2025-01-25",
            "qwen-turbo",
            "qwen-plus",
            "qwen-max"
        ]
        
        for model in supported_models:
            llm = DashscopeLLM(model_name=model)
            assert llm.model_name == model

    def test_search_options_default(self):
        """Test default search options configuration"""
        llm = DashscopeLLM(model_name="qwen-plus-2025-04-28")
        
        expected_options = {
            "forced_search": False,
            "enable_source": True,
            "enable_citation": False,
            "search_strategy": "pro"
        }
        
        assert llm.search_options == expected_options

    def test_search_options_custom(self):
        """Test custom search options configuration"""
        custom_options = {
            "forced_search": True,
            "enable_source": False,
            "enable_citation": True,
            "search_strategy": "basic"
        }
        
        llm = DashscopeLLM(
            model_name="qwen-plus-2025-04-28",
            search_options=custom_options
        )
        
        assert llm.search_options == custom_options


if __name__ == "__main__":
    # Run basic tests without pytest
    test_instance = TestDashscopeLLM()
    
    print("Running DashscopeLLM tests...")
    
    try:
        test_instance.test_initialization()
        print("✓ Initialization test passed")
        
        test_instance.test_initialization_with_custom_params()
        print("✓ Custom parameters test passed")
        
        test_instance.test_convert_messages_to_dashscope()
        print("✓ Message conversion test passed")
        
        test_instance.test_convert_tools_to_dashscope()
        print("✓ Tool conversion test passed")
        
        test_instance.test_convert_tools_to_dashscope_empty()
        print("✓ Empty tool conversion test passed")
        
        test_instance.test_model_name_validation()
        print("✓ Model name validation test passed")
        
        test_instance.test_search_options_default()
        print("✓ Default search options test passed")
        
        test_instance.test_search_options_custom()
        print("✓ Custom search options test passed")
        
        print("\nAll tests passed! 🎉")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
