"""Test script for LiteLLM.

This script provides test functions for both synchronous and asynchronous
chat operations. It can be run directly with: python test_lite_llm.py

Requires proper environment variables:
- FLOW_LLM_API_KEY: API key for authentication
- FLOW_LLM_BASE_URL: Base URL for the API endpoint
"""

import asyncio

from flowllm.core.enumeration import Role
from flowllm.core.llm.lite_llm import LiteLLM
from flowllm.core.schema import Message
from flowllm.core.utils import load_env

load_env()


async def async_main():
    """Async test function for LiteLLM.

    This function demonstrates how to use the LiteLLM class
    with async operations. It requires proper environment variables
    to be set for the chosen LLM provider.
    """

    # Example with OpenAI model through LiteLLM
    model_name = "qwen-max-2025-01-25"
    llm = LiteLLM(model_name=model_name)

    # Test async chat
    message: Message = await llm.achat(
        [Message(role=Role.USER, content="Hello! How are you?")],
        [],
        enable_stream_print=True,
    )
    print("\nAsync result:", message)


def main():
    """Sync test function for LiteLLM.

    This function demonstrates how to use the LiteLLM class
    with synchronous operations. It requires proper environment variables
    to be set for the chosen LLM provider.
    """

    # Example with OpenAI model through LiteLLM
    model_name = "qwen-max-2025-01-25"  # LiteLLM will route to OpenAI
    llm = LiteLLM(model_name=model_name)

    # Test sync chat
    message: Message = llm.chat(
        [Message(role=Role.USER, content="Hello! How are you?")],
        [],
        enable_stream_print=True,
    )
    print("\nSync result:", message)


if __name__ == "__main__":
    # Run async test by default
    asyncio.run(async_main())

    main()
