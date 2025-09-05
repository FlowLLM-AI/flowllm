import asyncio
import time
from abc import ABC
from typing import List, Callable

from loguru import logger
from pydantic import Field, BaseModel

from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall


class BaseLLM(BaseModel, ABC):
    """
    Abstract base class for Large Language Model (LLM) implementations.
    
    This class defines the common interface and configuration parameters
    that all LLM implementations should support. It provides a standardized
    way to interact with different LLM providers while handling common
    concerns like retries, error handling, and streaming.
    """
    # Core model configuration
    model_name: str = Field(..., description="Name of the LLM model to use")

    # Generation parameters
    seed: int = Field(default=42, description="Random seed for reproducible outputs")
    top_p: float | None = Field(default=None, description="Top-p (nucleus) sampling parameter")
    # stream: bool = Field(default=True)  # Commented out - streaming is handled per request
    stream_options: dict = Field(default={"include_usage": True}, description="Options for streaming responses")
    temperature: float = Field(default=0.0000001, description="Sampling temperature (low for deterministic outputs)")
    presence_penalty: float | None = Field(default=None, description="Presence penalty to reduce repetition")

    # Model-specific features
    enable_thinking: bool = Field(default=False, description="Enable reasoning/thinking mode for supported models")

    # Tool usage configuration
    tool_choice: str = Field(default=None, description="Strategy for tool selection")
    parallel_tool_calls: bool = Field(default=True, description="Allow multiple tool calls in parallel")

    # Error handling and reliability
    max_retries: int = Field(default=5, description="Maximum number of retry attempts on failure")
    raise_exception: bool = Field(default=False, description="Whether to raise exceptions or return default values")

    def stream_chat(self, messages: List[Message], tools: List[ToolCall] = None, **kwargs):
        """
        Stream chat completions from the LLM.
        
        This method should yield chunks of the response as they become available,
        allowing for real-time display of the model's output.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tools the model can use
            **kwargs: Additional model-specific parameters
            
        Yields:
            Chunks of the streaming response with their types
        """
        raise NotImplementedError

    async def astream_chat(self, messages: List[Message], tools: List[ToolCall] = None, **kwargs):
        """
        Async stream chat completions from the LLM.
        
        This method should yield chunks of the response as they become available,
        allowing for real-time display of the model's output in async contexts.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tools the model can use
            **kwargs: Additional model-specific parameters
            
        Yields:
            Chunks of the streaming response with their types
        """
        raise NotImplementedError

    def _chat(self, messages: List[Message], tools: List[ToolCall] = None, enable_stream_print: bool = False,
              **kwargs) -> Message:
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

    async def _achat(self, messages: List[Message], tools: List[ToolCall] = None, enable_stream_print: bool = False,
                     **kwargs) -> Message:
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

    def chat(self, messages: List[Message], tools: List[ToolCall] = None, enable_stream_print: bool = False,
             callback_fn: Callable = None, default_value=None, **kwargs):
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
                message: Message = self._chat(messages=messages,
                                              tools=tools,
                                              enable_stream_print=enable_stream_print,
                                              **kwargs)

                # Apply callback function if provided
                if callback_fn:
                    return callback_fn(message)
                else:
                    return message

            except Exception as e:
                logger.exception(f"chat with model={self.model_name} encounter error with e={e.args}")

                time.sleep(1 + i)

                if i == self.max_retries - 1:
                    if self.raise_exception:
                        raise e
                    else:
                        return default_value

        return None

    async def achat(self, messages: List[Message], tools: List[ToolCall] = None, enable_stream_print: bool = False,
                    callback_fn: Callable = None, default_value=None, **kwargs):
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
                message: Message = await self._achat(messages=messages,
                                                     tools=tools,
                                                     enable_stream_print=enable_stream_print,
                                                     **kwargs)

                # Apply callback function if provided
                if callback_fn:
                    return callback_fn(message)
                else:
                    return message

            except Exception as e:
                logger.exception(f"async chat with model={self.model_name} encounter error with e={e.args}")

                # Exponential backoff: wait longer after each failure
                await asyncio.sleep(1 + i)

                # Handle final retry failure
                if i == self.max_retries - 1:
                    if self.raise_exception:
                        raise e
                    else:
                        return default_value

        return None
