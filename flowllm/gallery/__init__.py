"""Gallery package for FlowLLM framework.

This package provides pre-built operations that can be used in LLM-powered flows.
It includes ready-to-use operations for:

- ChatOp: Interactive chat conversations with LLM
- StreamChatOp: Async operation for streaming chat responses from an LLM
- ExecuteCodeOp: Dynamic Python code execution for analysis and calculation
- GenSystemPromptOp: Generate optimized system prompts using LLM
- MockSearchOp: Mock search operation that uses LLM to generate search results
- DashscopeSearchOp: Web search operation using Dashscope API for retrieving internet information
- ReactSearchOp: ReAct (Reasoning and Acting) agent for answering queries using search tools

Typical usage:
    from flowllm.gallery import (
        ExecuteCodeOp,
        ChatOp,
        StreamChatOp,
        GenSystemPromptOp,
        MockSearchOp,
        DashscopeSearchOp,
        ReactSearchOp,
    )
    from flowllm.core.context import C

    # Operations are automatically registered via @C.register_op() decorator
"""

from .chat_op import ChatOp
from .dashscope_search_op import DashscopeSearchOp
from .execute_code_op import ExecuteCodeOp
from .gen_system_prompt_op import GenSystemPromptOp
from .mock_search_op import MockSearchOp
from .react_search_op import ReactSearchOp
from .stream_chat_op import StreamChatOp

__all__ = [
    "ChatOp",
    "DashscopeSearchOp",
    "ExecuteCodeOp",
    "GenSystemPromptOp",
    "MockSearchOp",
    "ReactSearchOp",
    "StreamChatOp",
]
