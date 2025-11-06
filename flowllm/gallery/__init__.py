"""Gallery package for FlowLLM framework.

This package provides pre-built operations that can be used in LLM-powered flows.
It includes ready-to-use operations for:

- ChatOp: Interactive chat conversations with LLM
- StreamChatOp: Async operation for streaming chat responses from an LLM
- ExecuteCodeOp: Dynamic Python code execution for analysis and calculation
- GenSystemPromptOp: Generate optimized system prompts using LLM
- MockSearchOp: Mock search operation that uses LLM to generate search results

Typical usage:
    from flowllm.gallery import ExecuteCodeOp, ChatOp, StreamChatOp, GenSystemPromptOp, MockSearchOp
    from flowllm.core.context import C

    # Operations are automatically registered via @C.register_op() decorator
"""

from .chat_op import ChatOp
from .execute_code_op import ExecuteCodeOp
from .gen_system_prompt_op import GenSystemPromptOp
from .mock_search_op import MockSearchOp
from .stream_chat_op import StreamChatOp

__all__ = [
    "ChatOp",
    "ExecuteCodeOp",
    "GenSystemPromptOp",
    "MockSearchOp",
    "StreamChatOp",
]
