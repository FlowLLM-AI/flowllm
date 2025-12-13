"""Base LLM class definition for flowllm.

This module defines the BaseLLM abstract base class that serves as the
foundation for all LLM implementations in the flowllm framework. It provides
a standardized interface for interacting with various LLM providers while
handling common concerns like retries, error handling, and streaming.
"""

import asyncio
import time
from abc import ABC
from typing import List, Callable, Optional, Generator, AsyncGenerator, Union, Any

from loguru import logger

from ..schema import FlowStreamChunk
from ..schema import Message
from ..schema import ToolCall


class BaseLLM(ABC):
    """
    Abstract base class for Large Language Model (LLM) implementations.

    This class defines the common interface and configuration parameters
    that all LLM implementations should support. It provides a standardized
    way to interact with different LLM providers while handling common
    concerns like retries, error handling, and streaming.
    """

    def __init__(self, model_name: str, max_retries: int = 5, raise_exception: bool = False, **kwargs):
        """
        Initialize the BaseLLM.

        Args:
            model_name: Name of the LLM model to use
            max_retries: Maximum number of retry attempts on failure
            raise_exception: Whether to raise exceptions or return default values
        """
        self.model_name: str = model_name
        self.max_retries: int = max_retries
        self.raise_exception: bool = raise_exception
        self.kwargs: dict = kwargs
        # ref: https://help.aliyun.com/zh/model-studio/qwen-api-reference

    def stream_chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        **kwargs,
    ) -> Generator[FlowStreamChunk, None, None]:
        """
        Stream chat completions from the LLM.

        This method should yield chunks of the response as they become available,
        allowing for real-time display of the model's output.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools the model can use
            **kwargs: Additional model-specific parameters

        Yields:
            FlowStreamChunk for each streaming piece.
            FlowStreamChunk contains chunk_type, chunk content, and metadata.
        """
        raise NotImplementedError

    async def astream_chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        **kwargs,
    ) -> AsyncGenerator[FlowStreamChunk, None]:
        """
        Async stream chat completions from the LLM.

        This method should yield chunks of the response as they become available,
        allowing for real-time display of the model's output in async contexts.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools the model can use
            **kwargs: Additional model-specific parameters

        Yields:
            FlowStreamChunk for each streaming piece.
            FlowStreamChunk contains chunk_type, chunk content, and metadata.
        """
        raise NotImplementedError

    def _chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        enable_stream_print: bool = False,
        **kwargs,
    ) -> Message:
        """
        Internal method to perform a single chat completion.

        This method should be implemented by subclasses to handle the actual
        communication with the LLM provider. It's called by the public chat()
        method which adds retry logic and error handling.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools the model can use
            enable_stream_print: Whether to print streaming response to console
            **kwargs: Additional model-specific parameters

        Returns:
            The complete response message from the LLM
        """
        raise NotImplementedError

    async def _achat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        enable_stream_print: bool = False,
        **kwargs,
    ) -> Message:
        """
        Internal async method to perform a single chat completion.

        This method should be implemented by subclasses to handle the actual
        async communication with the LLM provider. It's called by the public achat()
        method which adds retry logic and error handling.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools the model can use
            enable_stream_print: Whether to print streaming response to console
            **kwargs: Additional model-specific parameters

        Returns:
            The complete response message from the LLM
        """
        raise NotImplementedError

    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        enable_stream_print: bool = False,
        callback_fn: Optional[Callable[[Message], Any]] = None,
        default_value: Any = None,
        **kwargs,
    ) -> Union[Message, Any]:
        """
        Perform a chat completion with retry logic and error handling.

        This is the main public interface for chat completions. It wraps the
        internal _chat() method with robust error handling, exponential backoff,
        and optional callback processing.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools the model can use
            callback_fn: Optional callback to process the response message
            default_value: Value to return if all retries fail (when raise_exception=False)
            enable_stream_print: Whether to print streaming response to console
            **kwargs: Additional model-specific parameters

        Returns:
            The response message (possibly processed by callback_fn) or default_value

        Raises:
            Exception: If raise_exception=True and all retries fail
        """
        for i in range(self.max_retries):
            try:
                # Attempt to get response from the model
                message: Message = self._chat(
                    messages=messages,
                    tools=tools,
                    enable_stream_print=enable_stream_print,
                    **kwargs,
                )

                # Apply callback function if provided
                if callback_fn:
                    return callback_fn(message)
                else:
                    return message

            except Exception as e:
                logger.exception(f"chat with model={self.model_name} encounter error with e={e.args}")

                # If this is the last retry attempt, handle final failure
                if i == self.max_retries - 1:
                    if self.raise_exception:
                        raise e
                    # If raise_exception=False, return default_value without waiting
                    return default_value

                # Exponential backoff: wait before next retry attempt
                time.sleep(1 + i)

        return default_value

    async def achat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        enable_stream_print: bool = False,
        callback_fn: Optional[Callable[[Message], Any]] = None,
        default_value: Any = None,
        **kwargs,
    ) -> Union[Message, Any]:
        """
        Perform an async chat completion with retry logic and error handling.

        This is the main public interface for async chat completions. It wraps the
        internal _achat() method with robust error handling, exponential backoff,
        and optional callback processing.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools the model can use
            callback_fn: Optional callback to process the response message
            default_value: Value to return if all retries fail (when raise_exception=False)
            enable_stream_print: Whether to print streaming response to console
            **kwargs: Additional model-specific parameters

        Returns:
            The response message (possibly processed by callback_fn) or default_value

        Raises:
            Exception: If raise_exception=True and all retries fail
        """
        for i in range(self.max_retries):
            try:
                # Attempt to get response from the model
                message: Message = await self._achat(
                    messages=messages,
                    tools=tools,
                    enable_stream_print=enable_stream_print,
                    **kwargs,
                )

                # Apply callback function if provided
                if callback_fn:
                    return callback_fn(message)
                else:
                    return message

            except Exception as e:
                logger.exception(f"async chat with model={self.model_name} encounter error with e={e.args}")

                # If this is the last retry attempt, handle final failure
                if i == self.max_retries - 1:
                    if self.raise_exception:
                        raise e
                    # If raise_exception=False, return default_value without waiting
                    return default_value

                # Exponential backoff: wait before next retry attempt
                await asyncio.sleep(1 + i)

        return default_value

    def close(self):
        """Close the client connection or clean up resources."""

    async def async_close(self):
        """Asynchronously close the client connection or clean up resources."""
