"""OpenAI-compatible LLM implementation for flowllm.

This module provides an implementation of BaseLLM that supports OpenAI-compatible
APIs. It handles streaming responses, tool calling, and reasoning content from
supported models. The implementation supports both synchronous and asynchronous
operations with robust error handling and retry logic.
"""

import asyncio
import json
import os
import time
from typing import List, Dict, Optional, Generator, AsyncGenerator

from loguru import logger
from openai import OpenAI, AsyncOpenAI
from pydantic import Field, PrivateAttr, model_validator

from .base_llm import BaseLLM
from ..context import C
from ..enumeration import ChunkEnum
from ..enumeration import Role
from ..schema import FlowStreamChunk
from ..schema import Message
from ..schema import ToolCall


@C.register_llm("openai_compatible")
class OpenAICompatibleLLM(BaseLLM):
    """
    OpenAI-compatible LLM implementation supporting streaming and tool calls.

    This class implements the BaseLLM interface for OpenAI-compatible APIs,
    including support for:
    - Streaming responses with different chunk types (thinking, answer, tools)
    - Tool calling with parallel execution
    - Reasoning/thinking content from supported models
    - Robust error handling and retries

    The class follows the BaseLLM interface strictly, implementing all required methods
    with proper type annotations and error handling consistent with the base class.

    The implementation aggregates streaming chunks internally in _chat() and _achat()
    methods, which are called by the base class's chat() and achat() methods that add
    retry logic and error handling. Reasoning content is separated from regular answer
    content and stored in the Message's reasoning_content field.
    """

    # API configuration
    api_key: str = Field(
        default_factory=lambda: os.getenv("FLOW_LLM_API_KEY"),
        description="API key for authentication",
    )
    base_url: str = Field(
        default_factory=lambda: os.getenv("FLOW_LLM_BASE_URL"),
        description="Base URL for the API endpoint",
    )
    _client: OpenAI = PrivateAttr()
    _aclient: AsyncOpenAI = PrivateAttr()

    @model_validator(mode="after")
    def init_client(self):
        """
        Initialize the OpenAI clients after model validation.

        This validator runs after all field validation is complete,
        ensuring we have valid API credentials before creating the clients.

        Returns:
            Self for method chaining
        """
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self._aclient = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        return self

    def stream_chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        **kwargs,
    ) -> Generator[FlowStreamChunk, None, None]:
        """
        Stream chat completions from OpenAI-compatible API.

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
            Tuple of (chunk_content, ChunkEnum) for each streaming piece.
            chunk_content can be a string (for ANSWER/THINK), ToolCall (for TOOL),
            usage object (for USAGE), or error string (for ERROR).
        """
        for i in range(self.max_retries):
            try:
                extra_body = {}
                if self.enable_thinking:
                    extra_body["enable_thinking"] = True  # qwen3 params

                completion = self._client.chat.completions.create(
                    model=self.model_name,
                    messages=[x.simple_dump() for x in messages],
                    seed=self.seed,
                    top_p=self.top_p,
                    stream=True,
                    stream_options=self.stream_options,
                    temperature=self.temperature,
                    extra_body=extra_body,
                    tools=[x.simple_input_dump() for x in tools] if tools else None,
                    parallel_tool_calls=self.parallel_tool_calls,
                )

                # Initialize tool call tracking
                ret_tools: List[ToolCall] = []  # Accumulate tool calls across chunks
                is_answering: bool = False  # Track when model starts answering

                # Process each chunk in the streaming response
                for chunk in completion:
                    # Handle chunks without choices (usually usage info)
                    if not chunk.choices:
                        yield FlowStreamChunk(chunk_type=ChunkEnum.USAGE, chunk=chunk.usage.model_dump())

                    else:
                        delta = chunk.choices[0].delta

                        # Handle reasoning/thinking content (model's internal thoughts)
                        if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                            yield FlowStreamChunk(chunk_type=ChunkEnum.THINK, chunk=delta.reasoning_content)

                        else:
                            # Mark transition from thinking to answering
                            if not is_answering:
                                is_answering = True

                            # Handle regular response content
                            if delta.content is not None:
                                yield FlowStreamChunk(chunk_type=ChunkEnum.ANSWER, chunk=delta.content)

                            # Handle tool calls (function calling)
                            if delta.tool_calls is not None:
                                for tool_call in delta.tool_calls:
                                    index = tool_call.index

                                    # Ensure we have enough tool call slots
                                    while len(ret_tools) <= index:
                                        ret_tools.append(ToolCall(index=index))

                                    # Accumulate tool call information across chunks
                                    if tool_call.id:
                                        ret_tools[index].id += tool_call.id

                                    if tool_call.function and tool_call.function.name:
                                        ret_tools[index].name += tool_call.function.name

                                    if tool_call.function and tool_call.function.arguments:
                                        ret_tools[index].arguments += tool_call.function.arguments

                # Yield completed tool calls after streaming finishes
                if ret_tools:
                    tool_dict: Dict[str, ToolCall] = {x.name: x for x in tools} if tools else {}
                    for tool in ret_tools:
                        # Only yield tool calls that correspond to available tools
                        if tool.name not in tool_dict:
                            continue

                        if not tool.check_argument():
                            raise ValueError(f"Tool call {tool.name} argument={tool.arguments} are invalid")

                        yield FlowStreamChunk(chunk_type=ChunkEnum.TOOL, chunk=tool.simple_output_dump())

                return

            except Exception as e:
                logger.exception(f"stream chat with model={self.model_name} encounter error with e={e.args}")

                # If this is the last retry attempt, handle final failure
                if i == self.max_retries - 1:
                    if self.raise_exception:
                        raise e

                    yield FlowStreamChunk(chunk_type=ChunkEnum.ERROR, chunk=str(e))
                    return

                yield FlowStreamChunk(chunk_type=ChunkEnum.ERROR, chunk=str(e))
                time.sleep(1 + i)  # Wait before next retry

    async def astream_chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolCall]] = None,
        **kwargs,
    ) -> AsyncGenerator[FlowStreamChunk, None]:
        """
        Async stream chat completions from OpenAI-compatible API.

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
        for i in range(self.max_retries):
            try:
                extra_body = {}
                if self.enable_thinking:
                    extra_body["enable_thinking"] = True  # qwen3 params

                completion = await self._aclient.chat.completions.create(
                    model=self.model_name,
                    messages=[x.simple_dump() for x in messages],
                    seed=self.seed,
                    top_p=self.top_p,
                    stream=True,
                    stream_options=self.stream_options,
                    temperature=self.temperature,
                    extra_body=extra_body,
                    tools=[x.simple_input_dump() for x in tools] if tools else None,
                    parallel_tool_calls=self.parallel_tool_calls,
                )

                # Initialize tool call tracking
                ret_tools: List[ToolCall] = []  # Accumulate tool calls across chunks
                is_answering: bool = False  # Track when model starts answering

                # Process each chunk in the streaming response
                async for chunk in completion:
                    # Handle chunks without choices (usually usage info)
                    if not chunk.choices:
                        yield FlowStreamChunk(chunk_type=ChunkEnum.USAGE, chunk=chunk.usage.model_dump())

                    else:
                        delta = chunk.choices[0].delta

                        # Handle reasoning/thinking content (model's internal thoughts)
                        if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                            yield FlowStreamChunk(chunk_type=ChunkEnum.THINK, chunk=delta.reasoning_content)

                        else:
                            # Mark transition from thinking to answering
                            if not is_answering:
                                is_answering = True

                            # Handle regular response content
                            if delta.content is not None:
                                yield FlowStreamChunk(chunk_type=ChunkEnum.ANSWER, chunk=delta.content)

                            # Handle tool calls (function calling)
                            if delta.tool_calls is not None:
                                for tool_call in delta.tool_calls:
                                    index = tool_call.index

                                    # Ensure we have enough tool call slots
                                    while len(ret_tools) <= index:
                                        ret_tools.append(ToolCall(index=index))

                                    # Accumulate tool call information across chunks
                                    if tool_call.id:
                                        ret_tools[index].id += tool_call.id

                                    if tool_call.function and tool_call.function.name:
                                        ret_tools[index].name += tool_call.function.name

                                    if tool_call.function and tool_call.function.arguments:
                                        ret_tools[index].arguments += tool_call.function.arguments

                # Yield completed tool calls after streaming finishes
                if ret_tools:
                    tool_dict: Dict[str, ToolCall] = {x.name: x for x in tools} if tools else {}
                    for tool in ret_tools:
                        # Only yield tool calls that correspond to available tools
                        if tool.name not in tool_dict:
                            continue

                        if not tool.check_argument():
                            raise ValueError(f"Tool call {tool.name} argument={tool.arguments} are invalid")

                        yield FlowStreamChunk(chunk_type=ChunkEnum.TOOL, chunk=tool.simple_output_dump())

                return

            except Exception as e:
                logger.exception(f"async stream chat with model={self.model_name} encounter error with e={e.args}")

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

        enter_think = False  # Whether we've started printing thinking content
        enter_answer = False  # Whether we've started printing answer content
        reasoning_content = ""  # Model's internal reasoning
        answer_content = ""  # Final response content
        tool_calls = []  # List of tool calls to execute

        # Consume streaming response and aggregate chunks by type
        for stream_chunk in self.stream_chat(messages, tools, **kwargs):
            if stream_chunk.chunk_type is ChunkEnum.USAGE:
                chunk = stream_chunk.chunk
                # Display token usage statistics
                if enable_stream_print:
                    print(f"\n<usage>{json.dumps(chunk, ensure_ascii=False, indent=2)}</usage>", flush=True)

            elif stream_chunk.chunk_type is ChunkEnum.THINK:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    # Format thinking/reasoning content
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
                        # Close thinking section if we were in it
                        if enter_think:
                            print("\n</think>", flush=True)
                    print(chunk, end="", flush=True)

                answer_content += chunk

            elif stream_chunk.chunk_type is ChunkEnum.TOOL:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    print(f"\n<tool>{json.dumps(chunk, ensure_ascii=False, indent=2)}</tool>", flush=True)

                tool_calls.append(chunk)

            elif stream_chunk.chunk_type is ChunkEnum.ERROR:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    # Display error information
                    print(f"\n<error>{chunk}</error>", flush=True)

        # Construct complete response message
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

        enter_think = False  # Whether we've started printing thinking content
        enter_answer = False  # Whether we've started printing answer content
        reasoning_content = ""  # Model's internal reasoning
        answer_content = ""  # Final response content
        tool_calls = []  # List of tool calls to execute

        # Consume async streaming response and aggregate chunks by type
        async for stream_chunk in self.astream_chat(messages, tools, **kwargs):
            if stream_chunk.chunk_type is ChunkEnum.USAGE:
                chunk = stream_chunk.chunk
                # Display token usage statistics
                if enable_stream_print:
                    print(f"\n<usage>{json.dumps(chunk, ensure_ascii=False, indent=2)}</usage>", flush=True)

            elif stream_chunk.chunk_type is ChunkEnum.THINK:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    # Format thinking/reasoning content
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
                        # Close thinking section if we were in it
                        if enter_think:
                            print("\n</think>", flush=True)
                    print(chunk, end="", flush=True)

                answer_content += chunk

            elif stream_chunk.chunk_type is ChunkEnum.TOOL:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    print(f"\n<tool>{json.dumps(chunk, ensure_ascii=False, indent=2)}</tool>", flush=True)

                tool_calls.append(chunk)

            elif stream_chunk.chunk_type is ChunkEnum.ERROR:
                chunk = stream_chunk.chunk
                if enable_stream_print:
                    # Display error information
                    print(f"\n<error>{chunk}</error>", flush=True)

        # Construct complete response message
        return Message(
            role=Role.ASSISTANT,
            reasoning_content=reasoning_content,
            content=answer_content,
            tool_calls=tool_calls,
        )
