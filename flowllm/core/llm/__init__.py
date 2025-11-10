"""LLM (Large Language Model) module for flowllm.

This module provides base classes and implementations for interacting with
various Large Language Model providers. It includes:

- BaseLLM: Abstract base class defining the common interface for all LLM implementations
- OpenAICompatibleLLM: Implementation for OpenAI-compatible APIs
- LiteLLM: Implementation using LiteLLM library for 100+ LLM providers

All implementations support:
- Streaming responses
- Tool/function calling
- Async operations
- Error handling and retries
"""

from .base_llm import BaseLLM
from .lite_llm import LiteLLM
from .openai_compatible_llm import OpenAICompatibleLLM

__all__ = [
    "BaseLLM",
    "LiteLLM",
    "OpenAICompatibleLLM",
]
