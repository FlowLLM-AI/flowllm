import asyncio
import os
from typing import List, Dict

from loguru import logger
from pydantic import Field, PrivateAttr, model_validator

from flowllm.context.service_context import C
from flowllm.enumeration.chunk_enum import ChunkEnum
from flowllm.enumeration.role import Role
from flowllm.llm.base_llm import BaseLLM
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall


@C.register_llm("litellm")
class LiteLLMBaseLLM(BaseLLM):
    """
    LiteLLM-compatible LLM implementation supporting multiple LLM providers through unified interface.
    
    This class implements the BaseLLM interface using LiteLLM, which provides:
    - Support for 100+ LLM providers (OpenAI, Anthropic, Cohere, Azure, etc.)
    - Streaming responses with different chunk types (content, tools, usage)
    - Tool calling with parallel execution support
    - Unified API across different providers
    - Robust error handling and retries
    
    LiteLLM automatically handles provider-specific authentication and request formatting.
    """

    # API configuration - LiteLLM handles provider-specific settings
    api_key: str = Field(default_factory=lambda: os.getenv("FLOW_LLM_API_KEY"),
                         description="API key for authentication")
    base_url: str = Field(default_factory=lambda: os.getenv("FLOW_LLM_BASE_URL"),
                          description="Base URL for custom endpoints")

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
            "base_url": self.base_url,  #.replace("/v1", "")
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

    def stream_chat(self, messages: List[Message], tools: List[ToolCall] = None, **kwargs):
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
            Tuple of (chunk_content, ChunkEnum) for each streaming piece
        """
        from litellm import completion
        for i in range(self.max_retries):
            try:
                # Prepare parameters for LiteLLM
                params = self._litellm_params.copy()
                params.update(kwargs)
                params.update({
                    "messages": [x.simple_dump() for x in messages],
                    "stream": True,
                })

                # Add tools if provided
                if tools:
                    params["tools"] = [x.simple_input_dump() for x in tools]
                    params["tool_choice"] = self.tool_choice if self.tool_choice else "auto"

                # Create streaming completion using LiteLLM
                completion_response = completion(**params)

                # Initialize tool call tracking
                ret_tools: List[ToolCall] = []  # Accumulate tool calls across chunks

                # Process each chunk in the streaming response
                for chunk in completion_response:
                    try:
                        # Handle chunks without choices (usually usage/metadata)
                        if not hasattr(chunk, 'choices') or not chunk.choices:
                            # Check for usage information
                            if hasattr(chunk, 'usage') and chunk.usage:
                                yield chunk.usage, ChunkEnum.USAGE
                            continue

                        delta = chunk.choices[0].delta

                        # Handle regular response content
                        if hasattr(delta, 'content') and delta.content is not None:
                            yield delta.content, ChunkEnum.ANSWER

                        # Handle tool calls (function calling)
                        if hasattr(delta, 'tool_calls') and delta.tool_calls is not None:
                            for tool_call in delta.tool_calls:
                                index = getattr(tool_call, 'index', 0)

                                # Ensure we have enough tool call slots
                                while len(ret_tools) <= index:
                                    ret_tools.append(ToolCall(index=index))

                                # Accumulate tool call information across chunks
                                if hasattr(tool_call, 'id') and tool_call.id:
                                    ret_tools[index].id += tool_call.id

                                if (hasattr(tool_call, 'function') and tool_call.function and
                                        hasattr(tool_call.function, 'name') and tool_call.function.name):
                                    ret_tools[index].name += tool_call.function.name

                                if (hasattr(tool_call, 'function') and tool_call.function and
                                        hasattr(tool_call.function, 'arguments') and tool_call.function.arguments):
                                    ret_tools[index].arguments += tool_call.function.arguments

                    except Exception as chunk_error:
                        logger.warning(f"Error processing chunk: {chunk_error}")
                        continue

                # Yield completed tool calls after streaming finishes
                if ret_tools:
                    tool_dict: Dict[str, ToolCall] = {x.name: x for x in tools} if tools else {}
                    for tool in ret_tools:
                        # Only yield tool calls that correspond to available tools
                        if tools and tool.name not in tool_dict:
                            continue

                        yield tool, ChunkEnum.TOOL

                return

            except Exception as e:
                logger.exception(f"stream chat with LiteLLM model={self.model_name} encounter error: {e}")

                if i == self.max_retries - 1 and self.raise_exception:
                    raise e
                else:
                    yield str(e), ChunkEnum.ERROR

    async def astream_chat(self, messages: List[Message], tools: List[ToolCall] = None, **kwargs):
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
            Tuple of (chunk_content, ChunkEnum) for each streaming piece
        """
        from litellm import acompletion
        for i in range(self.max_retries):
            try:
                # Prepare parameters for LiteLLM
                params = self._litellm_params.copy()
                params.update(kwargs)
                params.update({
                    "messages": [x.simple_dump() for x in messages],
                    "stream": True,
                })

                # Add tools if provided
                if tools:
                    params["tools"] = [x.simple_input_dump() for x in tools]
                    params["tool_choice"] = self.tool_choice if self.tool_choice else "auto"

                # Create async streaming completion using LiteLLM
                completion_response = await acompletion(**params)

                # Initialize tool call tracking
                ret_tools: List[ToolCall] = []  # Accumulate tool calls across chunks

                # Process each chunk in the async streaming response
                async for chunk in completion_response:
                    try:
                        # Handle chunks without choices (usually usage/metadata)
                        if not hasattr(chunk, 'choices') or not chunk.choices:
                            # Check for usage information
                            if hasattr(chunk, 'usage') and chunk.usage:
                                yield chunk.usage, ChunkEnum.USAGE
                            continue

                        delta = chunk.choices[0].delta

                        # Handle regular response content
                        if hasattr(delta, 'content') and delta.content is not None:
                            yield delta.content, ChunkEnum.ANSWER

                        # Handle tool calls (function calling)
                        if hasattr(delta, 'tool_calls') and delta.tool_calls is not None:
                            for tool_call in delta.tool_calls:
                                index = getattr(tool_call, 'index', 0)

                                # Ensure we have enough tool call slots
                                while len(ret_tools) <= index:
                                    ret_tools.append(ToolCall(index=index))

                                # Accumulate tool call information across chunks
                                if hasattr(tool_call, 'id') and tool_call.id:
                                    ret_tools[index].id += tool_call.id

                                if (hasattr(tool_call, 'function') and tool_call.function and
                                        hasattr(tool_call.function, 'name') and tool_call.function.name):
                                    ret_tools[index].name += tool_call.function.name

                                if (hasattr(tool_call, 'function') and tool_call.function and
                                        hasattr(tool_call.function, 'arguments') and tool_call.function.arguments):
                                    ret_tools[index].arguments += tool_call.function.arguments

                    except Exception as chunk_error:
                        logger.warning(f"Error processing async chunk: {chunk_error}")
                        continue

                # Yield completed tool calls after streaming finishes
                if ret_tools:
                    tool_dict: Dict[str, ToolCall] = {x.name: x for x in tools} if tools else {}
                    for tool in ret_tools:
                        # Only yield tool calls that correspond to available tools
                        if tools and tool.name not in tool_dict:
                            continue

                        yield tool, ChunkEnum.TOOL

                return

            except Exception as e:
                logger.exception(f"async stream chat with LiteLLM model={self.model_name} encounter error: {e}")

                # Handle retry logic with async sleep
                await asyncio.sleep(1 + i)

                if i == self.max_retries - 1 and self.raise_exception:
                    raise e
                else:
                    yield str(e), ChunkEnum.ERROR

    def _chat(self, messages: List[Message], tools: List[ToolCall] = None, enable_stream_print: bool = False,
              **kwargs) -> Message:
        """
        Perform a complete chat completion by aggregating streaming chunks from LiteLLM.
        
        This method consumes the entire streaming response and combines all
        chunks into a single Message object. It separates regular answer content
        and tool calls, providing a complete response.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            enable_stream_print: Whether to print streaming response to console
            **kwargs: Additional parameters passed to LiteLLM
            
        Returns:
            Complete Message with all content aggregated
        """
        answer_content = ""  # Final response content
        tool_calls = []  # List of tool calls to execute

        # Consume streaming response and aggregate chunks by type
        for chunk, chunk_enum in self.stream_chat(messages, tools, **kwargs):
            if chunk_enum is ChunkEnum.USAGE:
                # Display token usage statistics
                if enable_stream_print:
                    if hasattr(chunk, 'model_dump_json'):
                        print(f"\n<usage>{chunk.model_dump_json(indent=2)}</usage>")
                    else:
                        print(f"\n<usage>{chunk}</usage>")

            elif chunk_enum is ChunkEnum.ANSWER:
                if enable_stream_print:
                    print(chunk, end="")
                answer_content += chunk

            elif chunk_enum is ChunkEnum.TOOL:
                if enable_stream_print:
                    if hasattr(chunk, 'model_dump_json'):
                        print(f"\n<tool>{chunk.model_dump_json()}</tool>", end="")
                    else:
                        print(f"\n<tool>{chunk}</tool>", end="")
                tool_calls.append(chunk)

            elif chunk_enum is ChunkEnum.ERROR:
                if enable_stream_print:
                    print(f"\n<error>{chunk}</error>", end="")

        # Construct complete response message
        return Message(
            role=Role.ASSISTANT,
            content=answer_content,
            tool_calls=tool_calls
        )

    async def _achat(self, messages: List[Message], tools: List[ToolCall] = None, enable_stream_print: bool = False,
                     **kwargs) -> Message:
        """
        Perform an async complete chat completion by aggregating streaming chunks from LiteLLM.
        
        This method consumes the entire async streaming response and combines all
        chunks into a single Message object. It separates regular answer content
        and tool calls, providing a complete response.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            enable_stream_print: Whether to print streaming response to console
            **kwargs: Additional parameters passed to LiteLLM
            
        Returns:
            Complete Message with all content aggregated
        """
        answer_content = ""  # Final response content
        tool_calls = []  # List of tool calls to execute

        # Consume async streaming response and aggregate chunks by type
        async for chunk, chunk_enum in self.astream_chat(messages, tools, **kwargs):
            if chunk_enum is ChunkEnum.USAGE:
                # Display token usage statistics
                if enable_stream_print:
                    if hasattr(chunk, 'model_dump_json'):
                        print(f"\n<usage>{chunk.model_dump_json(indent=2)}</usage>")
                    else:
                        print(f"\n<usage>{chunk}</usage>")

            elif chunk_enum is ChunkEnum.ANSWER:
                if enable_stream_print:
                    print(chunk, end="")
                answer_content += chunk

            elif chunk_enum is ChunkEnum.TOOL:
                if enable_stream_print:
                    if hasattr(chunk, 'model_dump_json'):
                        print(f"\n<tool>{chunk.model_dump_json()}</tool>", end="")
                    else:
                        print(f"\n<tool>{chunk}</tool>", end="")
                tool_calls.append(chunk)

            elif chunk_enum is ChunkEnum.ERROR:
                if enable_stream_print:
                    print(f"\n<error>{chunk}</error>", end="")

        # Construct complete response message
        return Message(
            role=Role.ASSISTANT,
            content=answer_content,
            tool_calls=tool_calls
        )


async def async_main():
    """
    Async test function for LiteLLMBaseLLM.
    
    This function demonstrates how to use the LiteLLMBaseLLM class
    with async operations. It requires proper environment variables
    to be set for the chosen LLM provider.
    """
    from flowllm.utils.common_utils import load_env

    load_env()

    # Example with OpenAI model through LiteLLM
    model_name = "qwen-max-2025-01-25"  # LiteLLM will route to OpenAI
    llm = LiteLLMBaseLLM(model_name=model_name)

    # Test async chat
    message: Message = await llm.achat(
        [Message(role=Role.USER, content="Hello! How are you?")],
        [],
        enable_stream_print=True
    )
    print("\nAsync result:", message)


def main():
    """
    Sync test function for LiteLLMBaseLLM.
    
    This function demonstrates how to use the LiteLLMBaseLLM class
    with synchronous operations. It requires proper environment variables
    to be set for the chosen LLM provider.
    """
    from flowllm.utils.common_utils import load_env

    load_env()

    # Example with OpenAI model through LiteLLM
    model_name = "qwen-max-2025-01-25"  # LiteLLM will route to OpenAI
    llm = LiteLLMBaseLLM(model_name=model_name)

    # Test sync chat
    message: Message = llm.chat(
        [Message(role=Role.USER, content="Hello! How are you?")],
        [],
        enable_stream_print=True
    )
    print("\nSync result:", message)


if __name__ == "__main__":
    main()

    # import asyncio
    #
    # asyncio.run(async_main())
