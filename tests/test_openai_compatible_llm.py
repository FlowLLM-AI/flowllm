"""Test script for OpenAICompatibleLLM.

This script provides test functions for both synchronous and asynchronous
chat operations. It can be run directly with: python test_openai_compatible_llm.py

Requires proper environment variables:
- FLOW_LLM_API_KEY: API key for authentication
- FLOW_LLM_BASE_URL: Base URL for the API endpoint
"""

import asyncio

from flowllm.core.enumeration import Role
from flowllm.core.llm.openai_compatible_llm import OpenAICompatibleLLM
from flowllm.core.schema import Message
from flowllm.core.utils import load_env

load_env()


async def async_main():
    """Async test function for OpenAICompatibleLLM.

    This function demonstrates how to use the OpenAICompatibleLLM class
    with async operations. It requires proper environment variables
    (FLOW_LLM_API_KEY and FLOW_LLM_BASE_URL) to be set.
    """

    # model_name = "qwen-max-2025-01-25"
    model_name = "qwen3-30b-a3b-thinking-2507"
    llm = OpenAICompatibleLLM(model_name=model_name)

    # Test async chat
    message: Message = await llm.achat(
        [Message(role=Role.USER, content="hello")],
        [],
        enable_stream_print=True,
    )
    print("Async result:", message)


def main():
    """Synchronous test function for OpenAICompatibleLLM."""

    model_name = "qwen-max-2025-01-25"
    llm = OpenAICompatibleLLM(model_name=model_name)

    # Test sync chat
    message: Message = llm.chat(
        [Message(role=Role.USER, content="hello")],
        [],
        enable_stream_print=False,
    )
    print("Sync result:", message)


if __name__ == "__main__":
    # Run async test by default
    asyncio.run(async_main())

    main()
