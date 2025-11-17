"""Token counting adapters for FlowLLM runtimes.

This subpackage centralizes reusable helpers for estimating token usage across
different model providers and SDKs:

- ``BaseToken``: Provides a character-length heuristic, defaulting to len(content)/4.
- ``OpenAIToken``: Implements counting logic compatible with OpenAI/gpt-* APIs.
- ``HuggingFaceToken``: Uses HuggingFace tokenizers and chat templates.

Typical usage:
    from flowllm.core.token import OpenAIToken

The module-level ``__all__`` surfaces the primary token helpers for convenience.
"""

from .base_token import BaseToken
from .huggingface_token import HuggingFaceToken
from .openai_token import OpenAIToken

__all__ = [
    "BaseToken",
    "HuggingFaceToken",
    "OpenAIToken",
]
