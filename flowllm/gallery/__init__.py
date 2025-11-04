"""Gallery package for FlowLLM framework.

This package provides pre-built operations that can be used in LLM-powered flows.
It includes ready-to-use operations for:

- ExecuteCodeOp: Dynamic Python code execution for analysis and calculation
- LLMChatOp: Interactive chat conversations with LLM
- GenSystemPromptOp: Generate optimized system prompts using LLM

Typical usage:
    from flowllm.gallery import ExecuteCodeOp, LLMChatOp, GenSystemPromptOp
    from flowllm.core.context import C

    # Operations are automatically registered via @C.register_op() decorator
"""

from .execute_code_op import ExecuteCodeOp
from .gen_system_prompt_op import GenSystemPromptOp
from .llm_chat_op import LLMChatOp

__all__ = [
    "ExecuteCodeOp",
    "GenSystemPromptOp",
    "LLMChatOp",
]
