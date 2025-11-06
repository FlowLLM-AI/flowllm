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
    - Streaming responses with different chunk types (thinking, answer, tools)
    - Tool calling with parallel execution support
    - Unified API across different providers
    - Robust error handling and retries

    LiteLLM automatically handles provider-specific authentication and request formatting.
    The class follows the BaseLLM interface strictly, implementing all required methods
    with proper type annotations and error handling consistent with the base class.

    The implementation aggregates streaming chunks internally in _chat() and _achat()
    methods, which are called by the base class's chat() and achat() methods that add
    retry logic and error handling. Reasoning content is separated from regular answer
    content and stored in the Message's reasoning_content field.
    """

    # API configuration
    api_key: str = Field(
        default_factory=lambda: os.getenv("FLOW_LLM_API_KEY", ""),
        description="API key for authentication",
    )
    base_url: str = Field(
        default_factory=lambda: os.getenv("FLOW_LLM_BASE_URL"),
        description="Base URL for custom endpoints",
    )
    custom_llm_provider: str = Field(
        default="openai",
        description="Custom LLM provider name for LiteLLM routing",
    )
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
        self._litellm_params = {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model_name,
            "temperature": self.temperature,
            "seed": self.seed,
        }

        if self.top_p is not None:
            self._litellm_params["top_p"] = self.top_p
        if self.presence_penalty is not None:
            self._litellm_params["presence_penalty"] = self.presence_penalty
        if self.custom_llm_provider:
            self._litellm_params["custom_llm_provider"] = self.custom_llm_provider

        return self

    @staticmethod
    def _convert_usage_to_dict(usage) -> dict:
        """Convert usage object to dict to avoid Pydantic serialization warnings."""
        if usage is not None:
            if hasattr(usage, "model_dump"):
                return usage.model_dump()
            elif hasattr(usage, "dict"):
                return usage.dict()
            elif hasattr(usage, "__dict__"):
                return usage.__dict__
        return {}

    @staticmethod
    def _process_delta_chunk(
        delta,
        ret_tools: List[ToolCall],
        is_answering: bool,
    ) -> tuple[bool, List[FlowStreamChunk]]:
        """Process a delta chunk and return updated is_answering state and chunks to yield."""
        chunks_to_yield: List[FlowStreamChunk] = []

        if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
            chunks_to_yield.append(
                FlowStreamChunk(chunk_type=ChunkEnum.THINK, chunk=delta.reasoning_content),
            )
            return is_answering, chunks_to_yield

        is_answering_now = True if not is_answering else is_answering
        if delta.content is not None:
            chunks_to_yield.append(
                FlowStreamChunk(chunk_type=ChunkEnum.ANSWER, chunk=delta.content),
            )

        if delta.tool_calls is not None:
            for tool_call in delta.tool_calls:
                index = tool_call.index
                while len(ret_tools) <= index:
                    ret_tools.append(ToolCall(index=index))

                if tool_call.id:
                    ret_tools[index].id += tool_call.id
                if tool_call.function and tool_call.function.name:
                    ret_tools[index].name += tool_call.function.name
                if tool_call.function and tool_call.function.arguments:
                    ret_tools[index].arguments += tool_call.function.arguments

        return is_answering_now, chunks_to_yield

    @staticmethod
    def _validate_and_yield_tools(
        ret_tools: List[ToolCall],
        tools: Optional[List[ToolCall]],
    ) -> Generator[FlowStreamChunk, None, None]:
        """Validate tool calls and yield tool chunks."""
        if not ret_tools:
            return

        tool_dict: Dict[str, ToolCall] = {x.name: x for x in tools} if tools else {}
        for tool in ret_tools:
            if tool.name not in tool_dict:
                continue

            if not tool.check_argument():
                raise ValueError(
                    f"Tool call {tool.name} argument={tool.arguments} are invalid",
                )

            yield FlowStreamChunk(chunk_type=ChunkEnum.TOOL, chunk=tool)

    def stream_chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        **kwargs,
    ) -> Generator[FlowStreamChunk, None, None]:
        """
        Stream chat completions from LiteLLM.

        This method handles streaming responses and categorizes chunks into different types:
        - THINK: Reasoning/thinking content from the model
        - ANSWER: Regular response content
        - TOOL: Tool calls that need to be executed
        - USAGE: Token usage statistics
        - ERROR: Error information

        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            **kwargs: Additional parameters

        Yields:
            FlowStreamChunk for each streaming piece.
            FlowStreamChunk contains chunk_type, chunk content, and metadata.
        """
        from litellm import completion

        for i in range(self.max_retries):
            try:
                params = self._litellm_params.copy()
                params.update(kwargs)
                params.update(
                    {
                        "messages": [x.simple_dump() for x in messages],
                        "stream": True,
                    },
                )

                if self.enable_thinking:
                    params["extra_body"] = {"enable_thinking": True}

                if tools:
                    params["tools"] = [x.simple_input_dump() for x in tools]
                    params["tool_choice"] = self.tool_choice if self.tool_choice else "auto"

                completion_response = completion(**params)

                ret_tools: List[ToolCall] = []
                is_answering: bool = False

                for chunk in completion_response:
                    if not chunk.choices:
                        usage = self._convert_usage_to_dict(chunk.usage)
                        yield FlowStreamChunk(chunk_type=ChunkEnum.USAGE, chunk=usage)
                    else:
                        delta = chunk.choices[0].delta
                        is_answering, chunks_to_yield = self._process_delta_chunk(
                            delta,
                            ret_tools,
                            is_answering,
                        )
                        yield from chunks_to_yield

                yield from self._validate_and_yield_tools(ret_tools, tools)

                return

            except Exception as e:
                logger.exception(f"stream chat with LiteLLM model={self.model_name} encounter error: {e}")

                if i == self.max_retries - 1:
                    if self.raise_exception:
                        raise e
                    yield FlowStreamChunk(chunk_type=ChunkEnum.ERROR, chunk=str(e))
                    return

                yield FlowStreamChunk(chunk_type=ChunkEnum.ERROR, chunk=str(e))
                time.sleep(1 + i)

    @staticmethod
    async def _avalidate_and_yield_tools(
        ret_tools: List[ToolCall],
        tools: Optional[List[ToolCall]],
    ) -> AsyncGenerator[FlowStreamChunk, None]:
        """Validate tool calls and yield tool chunks asynchronously."""
        if not ret_tools:
            return

        tool_dict: Dict[str, ToolCall] = {x.name: x for x in tools} if tools else {}
        for tool in ret_tools:
            if tool.name not in tool_dict:
                continue

            if not tool.check_argument():
                raise ValueError(
                    f"Tool call {tool.name} argument={tool.arguments} are invalid",
                )

            yield FlowStreamChunk(chunk_type=ChunkEnum.TOOL, chunk=tool)

    async def astream_chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        **kwargs,
    ) -> AsyncGenerator[FlowStreamChunk, None]:
        """
        Async stream chat completions from LiteLLM.

        This method handles async streaming responses and categorizes chunks into different types:
        - THINK: Reasoning/thinking content from the model
        - ANSWER: Regular response content
        - TOOL: Tool calls that need to be executed
        - USAGE: Token usage statistics
        - ERROR: Error information

        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            **kwargs: Additional parameters

        Yields:
            FlowStreamChunk for each streaming piece.
            FlowStreamChunk contains chunk_type, chunk content, and metadata.
        """
        from litellm import acompletion

        for i in range(self.max_retries):
            try:
                params = self._litellm_params.copy()
                params.update(kwargs)
                params.update(
                    {
                        "messages": [x.simple_dump() for x in messages],
                        "stream": True,
                    },
                )

                if self.enable_thinking:
                    params["extra_body"] = {"enable_thinking": True}

                if tools:
                    params["tools"] = [x.simple_input_dump() for x in tools]
                    params["tool_choice"] = self.tool_choice if self.tool_choice else "auto"

                completion_response = await acompletion(**params)

                ret_tools: List[ToolCall] = []
                is_answering: bool = False

                async for chunk in completion_response:
                    if not chunk.choices:
                        usage = self._convert_usage_to_dict(chunk.usage)
                        yield FlowStreamChunk(chunk_type=ChunkEnum.USAGE, chunk=usage)
                    else:
                        delta = chunk.choices[0].delta
                        is_answering, chunks_to_yield = self._process_delta_chunk(
                            delta,
                            ret_tools,
                            is_answering,
                        )
                        for chunk_to_yield in chunks_to_yield:
                            yield chunk_to_yield

                async for tool_chunk in self._avalidate_and_yield_tools(ret_tools, tools):
                    yield tool_chunk

                return

            except Exception as e:
                logger.exception(f"async stream chat with LiteLLM model={self.model_name} encounter error: {e}")

                if i == self.max_retries - 1:
                    if self.raise_exception:
                        raise e
                    yield FlowStreamChunk(chunk_type=ChunkEnum.ERROR, chunk=str(e))
                    return

                yield FlowStreamChunk(chunk_type=ChunkEnum.ERROR, chunk=str(e))
                await asyncio.sleep(1 + i)

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
        and combines all chunks into a single Message object. It separates reasoning content,
        regular answer content, and tool calls, providing a complete response.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            enable_stream_print: Whether to print streaming response to console
            **kwargs: Additional parameters

        Returns:
            Complete Message with all content aggregated from streaming chunks
        """
        enter_think = False
        enter_answer = False
        reasoning_content = ""
        answer_content = ""
        tool_calls = []

        for stream_chunk in self.stream_chat(messages, tools, **kwargs):
            if stream_chunk.chunk_type is ChunkEnum.USAGE:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    if hasattr(chunk, "model_dump_json"):
                        print(f"\n<usage>{chunk.model_dump_json(indent=2)}</usage>", flush=True)
                    else:
                        print(f"\n<usage>{chunk}</usage>", flush=True)

            elif stream_chunk.chunk_type is ChunkEnum.THINK:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    if not enter_think:
                        enter_think = True
                        print("<think>\n", end="", flush=True)
                    print(chunk, end="", flush=True)

                reasoning_content += chunk

            elif stream_chunk.chunk_type is ChunkEnum.ANSWER:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    if not enter_answer:
                        enter_answer = True
                        if enter_think:
                            print("\n</think>", flush=True)
                    print(chunk, end="", flush=True)

                answer_content += chunk

            elif stream_chunk.chunk_type is ChunkEnum.TOOL:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    print(f"\n<tool>{chunk.model_dump_json()}</tool>", flush=True)

                tool_calls.append(chunk)

            elif stream_chunk.chunk_type is ChunkEnum.ERROR:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    print(f"\n<error>{chunk}</error>", flush=True)

        return Message(
            role=Role.ASSISTANT,
            reasoning_content=reasoning_content,
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
        and combines all chunks into a single Message object. It separates reasoning content,
        regular answer content, and tool calls, providing a complete response.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            enable_stream_print: Whether to print streaming response to console
            **kwargs: Additional parameters

        Returns:
            Complete Message with all content aggregated from streaming chunks
        """
        enter_think = False
        enter_answer = False
        reasoning_content = ""
        answer_content = ""
        tool_calls = []

        async for stream_chunk in self.astream_chat(messages, tools, **kwargs):
            if stream_chunk.chunk_type is ChunkEnum.USAGE:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    if hasattr(chunk, "model_dump_json"):
                        print(f"\n<usage>{chunk.model_dump_json(indent=2)}</usage>", flush=True)
                    else:
                        print(f"\n<usage>{chunk}</usage>", flush=True)

            elif stream_chunk.chunk_type is ChunkEnum.THINK:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    if not enter_think:
                        enter_think = True
                        print("<think>\n", end="", flush=True)
                    print(chunk, end="", flush=True)

                reasoning_content += chunk

            elif stream_chunk.chunk_type is ChunkEnum.ANSWER:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    if not enter_answer:
                        enter_answer = True
                        if enter_think:
                            print("\n</think>", flush=True)
                    print(chunk, end="", flush=True)

                answer_content += chunk

            elif stream_chunk.chunk_type is ChunkEnum.TOOL:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    print(f"\n<tool>{chunk.model_dump_json()}</tool>", flush=True)

                tool_calls.append(chunk)

            elif stream_chunk.chunk_type is ChunkEnum.ERROR:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    print(f"\n<error>{chunk}</error>", flush=True)

        return Message(
            role=Role.ASSISTANT,
            reasoning_content=reasoning_content,
            content=answer_content,
            tool_calls=tool_calls,
        )
