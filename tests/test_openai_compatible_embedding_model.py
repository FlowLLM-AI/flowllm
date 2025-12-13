"""Test script for OpenAICompatibleEmbeddingModel.

This script provides test functions for both synchronous and asynchronous
embedding operations. It can be run directly with: python test_openai_compatible_embedding_model.py

Requires proper environment variables:
- FLOW_EMBEDDING_API_KEY: API key for authentication
- FLOW_EMBEDDING_BASE_URL: Base URL for the API endpoint
"""

import asyncio

from flowllm.core.embedding_model.openai_compatible_embedding_model import (
    OpenAICompatibleEmbeddingModel,
)
from flowllm.core.utils import load_env

load_env()


def main():
    """Test function for synchronous embedding operations.

    This function demonstrates how to use OpenAICompatibleEmbeddingModel
    to generate embeddings for both single text strings and lists of text strings.
    """
    model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    res1 = model.get_embeddings(
        "The clothes are of good quality and look good, definitely worth the wait. I love them.",
    )
    res2 = model.get_embeddings(["aa", "bb"])
    print(res1)
    print(res2)


async def async_main():
    """Test function for asynchronous embedding operations.

    This function demonstrates how to use OpenAICompatibleEmbeddingModel
    to generate embeddings asynchronously for both single text strings
    and lists of text strings.
    """
    model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")

    # Test async single text embedding
    res1 = await model.async_get_embeddings(
        "The clothes are of good quality and look good, definitely worth the wait. I love them.",
    )

    # Test async batch text embedding
    res2 = await model.async_get_embeddings(["aa", "bb"])

    print("Async results:")
    print(res1)
    print(res2)


if __name__ == "__main__":
    # Run async test by default
    asyncio.run(async_main())

    main()
