"""Base token counting helper implementation.

This module defines the common base class for token counting utilities used
by language models. It provides a simple, model-agnostic implementation that
estimates token usage from message content and optional tools.
"""

import math
from typing import List

from loguru import logger

from ..context import C
from ..schema import Message, ToolCall


@C.register_token_counter("base")
class BaseToken:
    """Common base class for adapters that count tokens for a model.

    This class provides a lightweight, heuristic token counter that can be
    used as a default implementation when a model-specific tokenizer is not
    available. It estimates token usage based on the total character length of
    messages and tools.
    """

    def __init__(self, model_name: str, **kwargs):
        """Initialize the base token counter.

        Args:
            model_name: Name of the LLM, or the name / path of the
                pretrained model this counter is associated with.
            **kwargs: Additional model-specific configuration parameters.
                They are stored for potential use by subclasses but are not
                interpreted in this base implementation.
        """
        self.model_name: str = model_name
        self.kwargs: dict = kwargs

    def token_count(
        self,
        messages: List[Message],
        tools: List[ToolCall] | None = None,
        **_kwargs,
    ) -> int:
        """Estimate the token count for the provided messages and tools.

        This implementation uses a simple heuristic that divides the total
        number of characters by 4 to approximate token usage, which aligns
        roughly with many BPE-based tokenizers for English text.

        Args:
            messages: Conversation history to be sent to the model.
            tools: Optional list of tool call definitions associated with
                the request. Tool names, descriptions, and arguments are
                included in the character-based estimation.
            **_kwargs: Extra keyword arguments ignored by this base
                implementation but accepted for API compatibility with
                more advanced token counters.

        Returns:
            Estimated token count as a non-negative integer. Returns ``0``
            when there is no content to count.
        """
        total_chars = 0
        logger.info("token count: using rule")

        for message in messages:
            content = message.content
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="ignore")
            total_chars += len(content)

            if message.reasoning_content:
                total_chars += len(message.reasoning_content)

        if tools:
            for tool in tools:
                total_chars += len(tool.name)
                total_chars += len(tool.description)
                total_chars += len(tool.arguments)

        return math.ceil(total_chars / 4) if total_chars else 0
