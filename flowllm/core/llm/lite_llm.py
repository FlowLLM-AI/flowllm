"""LiteLLM implementation for flowllm.

This module provides an implementation of BaseLLM using the LiteLLM library,
which enables support for 100+ LLM providers through a unified interface.
LiteLLM automatically handles provider-specific authentication and request
formatting, making it easy to switch between different LLM providers without
code changes.
"""

import asyncio
import os
import time
from typing import List, Dict, Optional, Generator, AsyncGenerator

from loguru import logger
from pydantic import Field, PrivateAttr, model_validator

from .base_llm import BaseLLM
from ..context import C
from ..enumeration import ChunkEnum
from ..enumeration import Role
from ..schema import FlowStreamChunk
from ..schema import Message
from ..schema import ToolCall


@C.register_llm()
class LiteLLM(BaseLLM):
    """
    LiteLLM-compatible LLM implementation supporting multiple LLM providers through unified interface.

    This class implements the BaseLLM interface using LiteLLM, which provides:
    - Support for 100+ LLM providers (OpenAI, Anthropic, Cohere, Azure, etc.)
    - Streaming responses with different chunk types (content, tools, usage)
    - Tool calling with parallel execution support
    - Unified API across different providers
    - Robust error handling and retries

    LiteLLM automatically handles provider-specific authentication and request formatting.
    The class follows the BaseLLM interface strictly, implementing all required methods
    with proper type annotations and error handling consistent with the base class.

    The implementation aggregates streaming chunks internally in _chat() and _achat()
    methods, which are called by the base class's chat() and achat() methods that add
    retry logic and error handling.
    """

    # API configuration - LiteLLM handles provider-specific settings
    api_key: str = Field(
        default_factory=lambda: os.getenv("FLOW_LLM_API_KEY", ""),
        description="API key for authentication",
    )
    base_url: str = Field(
        default_factory=lambda: os.getenv("FLOW_LLM_BASE_URL"),
        description="Base URL for custom endpoints",
    )

    # LiteLLM specific configuration
    custom_llm_provider: str = Field(default="openai", description="Custom LLM provider name for LiteLLM routing")

    # Additional LiteLLM parameters
    timeout: float = Field(default=600, description="Request timeout in seconds")
    max_tokens: int = Field(default=None, description="Maximum tokens to generate")

    # Private attributes for LiteLLM configuration
    _litellm_params: dict = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def init_litellm_config(self):
        """
        Initialize LiteLLM configuration after model validation.

        This validator sets up LiteLLM-specific parameters and environment variables
        required for different providers. It configures authentication and routing
        based on the model name and provider settings.

        Returns:
            Self for method chaining
        """

        # Configure LiteLLM parameters
        self._litellm_params = {
            "api_key": self.api_key,
            "base_url": self.base_url,  # .replace("/v1", "")
            "model": self.model_name,
            "temperature": self.temperature,
            "seed": self.seed,
            "timeout": self.timeout,
        }

        # Add optional parameters
        if self.top_p is not None:
            self._litellm_params["top_p"] = self.top_p
        if self.max_tokens is not None:
            self._litellm_params["max_tokens"] = self.max_tokens
        if self.presence_penalty is not None:
            self._litellm_params["presence_penalty"] = self.presence_penalty
        if self.custom_llm_provider:
            self._litellm_params["custom_llm_provider"] = self.custom_llm_provider

        return self

    def stream_chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        **kwargs,
    ) -> Generator[FlowStreamChunk, None, None]:
        """
        Stream chat completions from LiteLLM with support for multiple providers.

        This method handles streaming responses and categorizes chunks into different types:
        - ANSWER: Regular response content from the model
        - TOOL: Tool calls that need to be executed
        - USAGE: Token usage statistics (when available)
        - ERROR: Error information from failed requests

        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            **kwargs: Additional parameters passed to LiteLLM

        Yields:
            FlowStreamChunk for each streaming piece.
            FlowStreamChunk contains chunk_type, chunk content, and metadata.
        """
        from litellm import completion

        for i in range(self.max_retries):
            try:
                # Prepare parameters for LiteLLM
                params = self._litellm_params.copy()
                params.update(kwargs)
                params.update(
                    {
                        "messages": [x.simple_dump() for x in messages],
                        "stream": True,
                    },
                )

                # Add tools if provided
                if tools:
                    params["tools"] = [x.simple_input_dump() for x in tools]
                    params["tool_choice"] = self.tool_choice if self.tool_choice else "auto"

                # Create streaming completion using LiteLLM
                completion_response = completion(**params)

                # Initialize tool call tracking
                # Tool calls are streamed incrementally across multiple chunks, so we
                # need to accumulate them until complete before yielding
                ret_tools: List[ToolCall] = []  # Accumulate tool calls across chunks

                # Process each chunk in the streaming response
                for chunk in completion_response:
                    try:
                        # Handle chunks without choices (usually usage/metadata)
                        if not hasattr(chunk, "choices") or not chunk.choices:
                            # Check for usage information
                            if hasattr(chunk, "usage") and chunk.usage:
                                yield FlowStreamChunk(chunk_type=ChunkEnum.USAGE, chunk=chunk.usage)
                            continue

                        delta = chunk.choices[0].delta

                        # Handle regular response content
                        if hasattr(delta, "content") and delta.content is not None:
                            yield FlowStreamChunk(chunk_type=ChunkEnum.ANSWER, chunk=delta.content)

                        # Handle tool calls (function calling)
                        if hasattr(delta, "tool_calls") and delta.tool_calls is not None:
                            for tool_call in delta.tool_calls:
                                index = getattr(tool_call, "index", 0)

                                # Ensure we have enough tool call slots for parallel tool calls
                                #  may be split across multiple chunks, so we accumulate
                                # the id, name, and arguments incrementally
                                while len(ret_tools) <= index:
                                    ret_tools.append(ToolCall(index=index))

                                # Accumulate tool call information across chunks
                                if hasattr(tool_call, "id") and tool_call.id:
                                    ret_tools[index].id += tool_call.id

                                if (
                                    hasattr(tool_call, "function")
                                    and tool_call.function
                                    and hasattr(tool_call.function, "name")
                                    and tool_call.function.name
                                ):
                                    ret_tools[index].name += tool_call.function.name

                                if (
                                    hasattr(tool_call, "function")
                                    and tool_call.function
                                    and hasattr(tool_call.function, "arguments")
                                    and tool_call.function.arguments
                                ):
                                    ret_tools[index].arguments += tool_call.function.arguments

                    except Exception as chunk_error:
                        logger.warning(f"Error processing chunk: {chunk_error}")
                        continue

                # Yield completed tool calls after streaming finishes
                # Tool calls are only yielded after all chunks are received and validated
                if ret_tools:
                    # Create a mapping of available tool names for validation
                    tool_dict: Dict[str, ToolCall] = {x.name: x for x in tools} if tools else {}
                    for tool in ret_tools:
                        # Only yield tool calls that correspond to available tools
                        if tools and tool.name not in tool_dict:
                            continue

                        # Validate tool call arguments before yielding
                        if not tool.check_argument():
                            raise ValueError(f"Tool call {tool.name} argument={tool.arguments} are invalid")

                        yield FlowStreamChunk(chunk_type=ChunkEnum.TOOL, chunk=tool)

                return

            except Exception as e:
                logger.exception(f"stream chat with LiteLLM model={self.model_name} encounter error: {e}")

                # If this is the last retry attempt, handle final failure
                if i == self.max_retries - 1:
                    if self.raise_exception:
                        raise e
                    # If raise_exception=False, yield error and stop retrying
                    yield FlowStreamChunk(chunk_type=ChunkEnum.ERROR, chunk=str(e))
                    return

                # Exponential backoff: wait before next retry attempt
                # Note: For streaming, we yield error and continue retrying
                yield FlowStreamChunk(chunk_type=ChunkEnum.ERROR, chunk=str(e))
                time.sleep(1 + i)  # Wait before next retry

    async def astream_chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        **kwargs,
    ) -> AsyncGenerator[FlowStreamChunk, None]:
        """
        Async stream chat completions from LiteLLM with support for multiple providers.

        This method handles async streaming responses and categorizes chunks into different types:
        - ANSWER: Regular response content from the model
        - TOOL: Tool calls that need to be executed
        - USAGE: Token usage statistics (when available)
        - ERROR: Error information from failed requests

        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            **kwargs: Additional parameters passed to LiteLLM

        Yields:
            FlowStreamChunk for each streaming piece.
            FlowStreamChunk contains chunk_type, chunk content, and metadata.
        """
        from litellm import acompletion

        for i in range(self.max_retries):
            try:
                # Prepare parameters for LiteLLM
                params = self._litellm_params.copy()
                params.update(kwargs)
                params.update(
                    {
                        "messages": [x.simple_dump() for x in messages],
                        "stream": True,
                    },
                )

                # Add tools if provided
                if tools:
                    params["tools"] = [x.simple_input_dump() for x in tools]
                    params["tool_choice"] = self.tool_choice if self.tool_choice else "auto"

                # Create async streaming completion using LiteLLM
                completion_response = await acompletion(**params)

                # Initialize tool call tracking
                # Tool calls are streamed incrementally across multiple chunks, so we
                # need to accumulate them until complete before yielding
                ret_tools: List[ToolCall] = []  # Accumulate tool calls across chunks

                # Process each chunk in the async streaming response
                async for chunk in completion_response:
                    try:
                        # Handle chunks without choices (usually usage/metadata)
                        if not hasattr(chunk, "choices") or not chunk.choices:
                            # Check for usage information
                            if hasattr(chunk, "usage") and chunk.usage:
                                yield FlowStreamChunk(chunk_type=ChunkEnum.USAGE, chunk=chunk.usage)
                            continue

                        delta = chunk.choices[0].delta

                        # Handle regular response content
                        if hasattr(delta, "content") and delta.content is not None:
                            yield FlowStreamChunk(chunk_type=ChunkEnum.ANSWER, chunk=delta.content)

                        # Handle tool calls (function calling)
                        if hasattr(delta, "tool_calls") and delta.tool_calls is not None:
                            for tool_call in delta.tool_calls:
                                index = getattr(tool_call, "index", 0)

                                # Ensure we have enough tool call slots for parallel tool calls
                                #  may be split across multiple chunks, so we accumulate
                                # the id, name, and arguments incrementally
                                while len(ret_tools) <= index:
                                    ret_tools.append(ToolCall(index=index))

                                # Accumulate tool call information across chunks
                                if hasattr(tool_call, "id") and tool_call.id:
                                    ret_tools[index].id += tool_call.id

                                if (
                                    hasattr(tool_call, "function")
                                    and tool_call.function
                                    and hasattr(tool_call.function, "name")
                                    and tool_call.function.name
                                ):
                                    ret_tools[index].name += tool_call.function.name

                                if (
                                    hasattr(tool_call, "function")
                                    and tool_call.function
                                    and hasattr(tool_call.function, "arguments")
                                    and tool_call.function.arguments
                                ):
                                    ret_tools[index].arguments += tool_call.function.arguments

                    except Exception as chunk_error:
                        logger.warning(f"Error processing async chunk: {chunk_error}")
                        continue

                # Yield completed tool calls after streaming finishes
                # Tool calls are only yielded after all chunks are received and validated
                if ret_tools:
                    # Create a mapping of available tool names for validation
                    tool_dict: Dict[str, ToolCall] = {x.name: x for x in tools} if tools else {}
                    for tool in ret_tools:
                        # Only yield tool calls that correspond to available tools
                        if tools and tool.name not in tool_dict:
                            continue

                        # Validate tool call arguments before yielding
                        if not tool.check_argument():
                            raise ValueError(f"Tool call {tool.name} argument={tool.arguments} are invalid")

                        yield FlowStreamChunk(chunk_type=ChunkEnum.TOOL, chunk=tool)

                return

            except Exception as e:
                logger.exception(f"async stream chat with LiteLLM model={self.model_name} encounter error: {e}")

                # If this is the last retry attempt, handle final failure
                if i == self.max_retries - 1:
                    if self.raise_exception:
                        raise e
                    # If raise_exception=False, yield error and stop retrying
                    yield FlowStreamChunk(chunk_type=ChunkEnum.ERROR, chunk=str(e))
                    return

                # Exponential backoff: wait before next retry attempt
                # Note: For streaming, we yield error and continue retrying
                yield FlowStreamChunk(chunk_type=ChunkEnum.ERROR, chunk=str(e))
                await asyncio.sleep(1 + i)  # Wait before next retry

    def _chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        enable_stream_print: bool = False,
        **kwargs,
    ) -> Message:
        """
        Internal method to perform a single chat completion by aggregating streaming chunks.

        This method is called by the base class's chat() method which adds retry logic
        and error handling. It consumes the entire streaming response from stream_chat()
        and combines all chunks into a single Message object. It separates regular answer
        content and tool calls, providing a complete response.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            enable_stream_print: Whether to print streaming response to console
            **kwargs: Additional parameters passed to LiteLLM

        Returns:
            Complete Message with all content aggregated from streaming chunks
        """
        answer_content = ""  # Final response content
        tool_calls = []  # List of tool calls to execute

        # Consume streaming response and aggregate chunks by type
        for stream_chunk in self.stream_chat(messages, tools, **kwargs):
            if stream_chunk.chunk_type is ChunkEnum.USAGE:
                chunk = stream_chunk.chunk
                # Display token usage statistics
                if enable_stream_print:
                    if hasattr(chunk, "model_dump_json"):
                        print(f"\n<usage>{chunk.model_dump_json(indent=2)}</usage>", flush=True)
                    else:
                        print(f"\n<usage>{chunk}</usage>", flush=True)

            elif stream_chunk.chunk_type is ChunkEnum.ANSWER:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    print(chunk, end="", flush=True)
                answer_content += chunk

            elif stream_chunk.chunk_type is ChunkEnum.TOOL:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    if hasattr(chunk, "model_dump_json"):
                        print(f"\n<tool>{chunk.model_dump_json()}</tool>", end="", flush=True)
                    else:
                        print(f"\n<tool>{chunk}</tool>", end="", flush=True)
                tool_calls.append(chunk)

            elif stream_chunk.chunk_type is ChunkEnum.ERROR:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    print(f"\n<error>{chunk}</error>", end="", flush=True)

        # Construct complete response message
        return Message(
            role=Role.ASSISTANT,
            content=answer_content,
            tool_calls=tool_calls,
        )

    async def _achat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        enable_stream_print: bool = False,
        **kwargs,
    ) -> Message:
        """
        Internal async method to perform a single chat completion by aggregating streaming chunks.

        This method is called by the base class's achat() method which adds retry logic
        and error handling. It consumes the entire async streaming response from astream_chat()
        and combines all chunks into a single Message object. It separates regular answer
        content and tool calls, providing a complete response.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            enable_stream_print: Whether to print streaming response to console
            **kwargs: Additional parameters passed to LiteLLM

        Returns:
            Complete Message with all content aggregated from streaming chunks
        """
        answer_content = ""  # Final response content
        tool_calls = []  # List of tool calls to execute

        # Consume async streaming response and aggregate chunks by type
        async for stream_chunk in self.astream_chat(messages, tools, **kwargs):
            if stream_chunk.chunk_type is ChunkEnum.USAGE:
                chunk = stream_chunk.chunk
                # Display token usage statistics
                if enable_stream_print:
                    if hasattr(chunk, "model_dump_json"):
                        print(f"\n<usage>{chunk.model_dump_json(indent=2)}</usage>", flush=True)
                    else:
                        print(f"\n<usage>{chunk}</usage>", flush=True)

            elif stream_chunk.chunk_type is ChunkEnum.ANSWER:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    print(chunk, end="", flush=True)
                answer_content += chunk

            elif stream_chunk.chunk_type is ChunkEnum.TOOL:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    if hasattr(chunk, "model_dump_json"):
                        print(f"\n<tool>{chunk.model_dump_json()}</tool>", end="", flush=True)
                    else:
                        print(f"\n<tool>{chunk}</tool>", end="", flush=True)
                tool_calls.append(chunk)

            elif stream_chunk.chunk_type is ChunkEnum.ERROR:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    print(f"\n<error>{chunk}</error>", end="", flush=True)

        # Construct complete response message
        return Message(
            role=Role.ASSISTANT,
            content=answer_content,
            tool_calls=tool_calls,
        )
