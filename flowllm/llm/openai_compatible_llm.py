import os
from typing import List, Dict

from loguru import logger
from openai import OpenAI, AsyncOpenAI
from openai.types import CompletionUsage
from pydantic import Field, PrivateAttr, model_validator

from flowllm.context.service_context import C
from flowllm.enumeration.chunk_enum import ChunkEnum
from flowllm.enumeration.role import Role
from flowllm.llm.base_llm import BaseLLM
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall


@C.register_llm("openai_compatible")
class OpenAICompatibleBaseLLM(BaseLLM):
    """
    OpenAI-compatible LLM implementation supporting streaming and tool calls.
    
    This class implements the BaseLLM interface for OpenAI-compatible APIs,
    including support for:
    - Streaming responses with different chunk types (thinking, answer, tools)
    - Tool calling with parallel execution
    - Reasoning/thinking content from supported models
    - Robust error handling and retries
    """

    # API configuration
    api_key: str = Field(default_factory=lambda: os.getenv("FLOW_LLM_API_KEY"),
                         description="API key for authentication")
    base_url: str = Field(default_factory=lambda: os.getenv("FLOW_LLM_BASE_URL"),
                          description="Base URL for the API endpoint")
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

    def stream_chat(self, messages: List[Message], tools: List[ToolCall] = None, **kwargs):
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
            Tuple of (chunk_content, ChunkEnum) for each streaming piece
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
                    parallel_tool_calls=self.parallel_tool_calls)

                # Initialize tool call tracking
                ret_tools: List[ToolCall] = []  # Accumulate tool calls across chunks
                is_answering: bool = False  # Track when model starts answering

                # Process each chunk in the streaming response
                for chunk in completion:
                    # Handle chunks without choices (usually usage info)
                    if not chunk.choices:
                        yield chunk.usage, ChunkEnum.USAGE

                    else:
                        delta = chunk.choices[0].delta

                        # Handle reasoning/thinking content (model's internal thoughts)
                        if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                            yield delta.reasoning_content, ChunkEnum.THINK

                        else:
                            # Mark transition from thinking to answering
                            if not is_answering:
                                is_answering = True

                            # Handle regular response content
                            if delta.content is not None:
                                yield delta.content, ChunkEnum.ANSWER

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

                        yield tool, ChunkEnum.TOOL

                return

            except Exception as e:
                logger.exception(f"stream chat with model={self.model_name} encounter error with e={e.args}")

                # Handle retry logic
                if i == self.max_retries - 1 and self.raise_exception:
                    raise e
                else:
                    yield str(e), ChunkEnum.ERROR

    async def astream_chat(self, messages: List[Message], tools: List[ToolCall] = None, **kwargs):
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
            Tuple of (chunk_content, ChunkEnum) for each streaming piece
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
                    parallel_tool_calls=self.parallel_tool_calls)

                # Initialize tool call tracking
                ret_tools: List[ToolCall] = []  # Accumulate tool calls across chunks
                is_answering: bool = False  # Track when model starts answering

                # Process each chunk in the streaming response
                async for chunk in completion:
                    # Handle chunks without choices (usually usage info)
                    if not chunk.choices:
                        yield chunk.usage, ChunkEnum.USAGE

                    else:
                        delta = chunk.choices[0].delta

                        # Handle reasoning/thinking content (model's internal thoughts)
                        if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                            yield delta.reasoning_content, ChunkEnum.THINK

                        else:
                            # Mark transition from thinking to answering
                            if not is_answering:
                                is_answering = True

                            # Handle regular response content
                            if delta.content is not None:
                                yield delta.content, ChunkEnum.ANSWER

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

                        yield tool, ChunkEnum.TOOL

                return

            except Exception as e:
                logger.exception(f"async stream chat with model={self.model_name} encounter error with e={e.args}")

                # Handle retry logic
                if i == self.max_retries - 1 and self.raise_exception:
                    raise e
                else:
                    yield str(e), ChunkEnum.ERROR

    def _chat(self, messages: List[Message], tools: List[ToolCall] = None, enable_stream_print: bool = False,
              **kwargs) -> Message:
        """
        Perform a complete chat completion by aggregating streaming chunks.
        
        This method consumes the entire streaming response and combines all
        chunks into a single Message object. It separates reasoning content,
        regular answer content, and tool calls.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            enable_stream_print: Whether to print streaming response to console
            **kwargs: Additional parameters
            
        Returns:
            Complete Message with all content aggregated
        """

        enter_think = False  # Whether we've started printing thinking content
        enter_answer = False  # Whether we've started printing answer content
        reasoning_content = ""  # Model's internal reasoning
        answer_content = ""  # Final response content
        tool_calls = []  # List of tool calls to execute

        # Consume streaming response and aggregate chunks by type
        for chunk, chunk_enum in self.stream_chat(messages, tools, **kwargs):
            if chunk_enum is ChunkEnum.USAGE:
                # Display token usage statistics
                if enable_stream_print:
                    if isinstance(chunk, CompletionUsage):
                        print(f"\n<usage>{chunk.model_dump_json(indent=2)}</usage>")
                    else:
                        print(f"\n<usage>{chunk}</usage>")

            elif chunk_enum is ChunkEnum.THINK:
                if enable_stream_print:
                    # Format thinking/reasoning content
                    if not enter_think:
                        enter_think = True
                        print("<think>\n", end="")
                    print(chunk, end="")

                reasoning_content += chunk

            elif chunk_enum is ChunkEnum.ANSWER:
                if enable_stream_print:
                    if not enter_answer:
                        enter_answer = True
                        # Close thinking section if we were in it
                        if enter_think:
                            print("\n</think>")
                    print(chunk, end="")

                answer_content += chunk

            elif chunk_enum is ChunkEnum.TOOL:
                if enable_stream_print:
                    print(f"\n<tool>{chunk.model_dump_json()}</tool>", end="")

                tool_calls.append(chunk)

            elif chunk_enum is ChunkEnum.ERROR:
                if enable_stream_print:
                    # Display error information
                    print(f"\n<error>{chunk}</error>", end="")

        # Construct complete response message
        return Message(role=Role.ASSISTANT,
                       reasoning_content=reasoning_content,
                       content=answer_content,
                       tool_calls=tool_calls)

    async def _achat(self, messages: List[Message], tools: List[ToolCall] = None, enable_stream_print: bool = False,
                     **kwargs) -> Message:
        """
        Perform an async complete chat completion by aggregating streaming chunks.
        
        This method consumes the entire async streaming response and combines all
        chunks into a single Message object. It separates reasoning content,
        regular answer content, and tool calls.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            enable_stream_print: Whether to print streaming response to console
            **kwargs: Additional parameters
            
        Returns:
            Complete Message with all content aggregated
        """

        enter_think = False  # Whether we've started printing thinking content
        enter_answer = False  # Whether we've started printing answer content
        reasoning_content = ""  # Model's internal reasoning
        answer_content = ""  # Final response content
        tool_calls = []  # List of tool calls to execute

        # Consume async streaming response and aggregate chunks by type
        async for chunk, chunk_enum in self.astream_chat(messages, tools, **kwargs):
            if chunk_enum is ChunkEnum.USAGE:
                # Display token usage statistics
                if enable_stream_print:
                    if isinstance(chunk, CompletionUsage):
                        print(f"\n<usage>{chunk.model_dump_json(indent=2)}</usage>")
                    else:
                        print(f"\n<usage>{chunk}</usage>")

            elif chunk_enum is ChunkEnum.THINK:
                if enable_stream_print:
                    # Format thinking/reasoning content
                    if not enter_think:
                        enter_think = True
                        print("<think>\n", end="")
                    print(chunk, end="")

                reasoning_content += chunk

            elif chunk_enum is ChunkEnum.ANSWER:
                if enable_stream_print:
                    if not enter_answer:
                        enter_answer = True
                        # Close thinking section if we were in it
                        if enter_think:
                            print("\n</think>")
                    print(chunk, end="")

                answer_content += chunk

            elif chunk_enum is ChunkEnum.TOOL:
                if enable_stream_print:
                    print(f"\n<tool>{chunk.model_dump_json()}</tool>", end="")

                tool_calls.append(chunk)

            elif chunk_enum is ChunkEnum.ERROR:
                if enable_stream_print:
                    # Display error information
                    print(f"\n<error>{chunk}</error>", end="")

        # Construct complete response message
        return Message(role=Role.ASSISTANT,
                       reasoning_content=reasoning_content,
                       content=answer_content,
                       tool_calls=tool_calls)


async def async_main():
    from flowllm.utils.common_utils import load_env

    load_env()

    # model_name = "qwen-max-2025-01-25"
    model_name = "qwen3-30b-a3b-thinking-2507"
    llm = OpenAICompatibleBaseLLM(model_name=model_name)

    # Test async chat
    message: Message = await llm.achat([Message(role=Role.USER, content="hello")], [],
                                       enable_stream_print=True)
    print("Async result:", message)


def main():
    from flowllm.utils.common_utils import load_env

    load_env()

    model_name = "qwen-max-2025-01-25"
    llm = OpenAICompatibleBaseLLM(model_name=model_name)

    # Test sync chat
    message: Message = llm.chat([Message(role=Role.USER, content="hello")], [],
                                enable_stream_print=False)
    print("Sync result:", message)


if __name__ == "__main__":
    # main()

    import asyncio
    asyncio.run(async_main())
