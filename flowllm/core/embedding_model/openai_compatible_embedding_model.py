"""OpenAI-compatible embedding model implementation.

This module provides an embedding model implementation that works with
OpenAI-compatible embedding APIs, including OpenAI's official API and
other services that follow the same interface.
"""

import os
from typing import Literal, List

from openai import OpenAI, AsyncOpenAI

from .base_embedding_model import BaseEmbeddingModel
from ..context import C


@C.register_embedding_model("openai_compatible")
class OpenAICompatibleEmbeddingModel(BaseEmbeddingModel):
    """
    OpenAI-compatible embedding model implementation.

    This class provides an implementation of BaseEmbeddingModel that works with
    OpenAI-compatible embedding APIs, including OpenAI's official API and
    other services that follow the same interface.

    Attributes:
        api_key: API key for authentication
        base_url: Base URL for the API endpoint
        encoding_format: Encoding format for embeddings ("float" or "base64")
    """

    def __init__(
        self,
        model_name: str = "",
        dimensions: int = 1024,
        max_batch_size: int = 10,
        max_retries: int = 3,
        raise_exception: bool = True,
        api_key: str | None = None,
        base_url: str | None = None,
        encoding_format: Literal["float", "base64"] = "float",
        **kwargs,
    ):
        """
        Initialize the OpenAI-compatible embedding model.

        Args:
            model_name: Name of the embedding model to use
            dimensions: Dimensionality of the embedding vectors
            api_key: API key for authentication (defaults to FLOW_EMBEDDING_API_KEY env var)
            base_url: Base URL for the API endpoint (defaults to FLOW_EMBEDDING_BASE_URL env var)
            encoding_format: Encoding format for embeddings
            max_retries: Maximum number of retry attempts on failure
            raise_exception: Whether to raise exceptions after max retries
            max_batch_size: Maximum batch size for processing
        """
        super().__init__(
            model_name=model_name,
            dimensions=dimensions,
            max_retries=max_retries,
            raise_exception=raise_exception,
            max_batch_size=max_batch_size,
            **kwargs,
        )
        self.api_key = api_key or os.getenv("FLOW_EMBEDDING_API_KEY", "")
        self.base_url = base_url or os.getenv("FLOW_EMBEDDING_BASE_URL", "")
        self.encoding_format = encoding_format

        # Initialize OpenAI clients
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self._async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def _get_embeddings(self, input_text: str | List[str]):
        """
        Get embeddings from the OpenAI-compatible API.

        This method implements the abstract _get_embeddings method from BaseEmbeddingModel
        by calling the OpenAI-compatible embeddings API.

        Args:
            input_text: Single text string or list of text strings to embed

        Returns:
            Embedding vector(s) corresponding to the input text(s)

        Raises:
            RuntimeError: If unsupported input type is provided
        """
        completion = self._client.embeddings.create(
            model=self.model_name,
            input=input_text,
            dimensions=self.dimensions,
            encoding_format=self.encoding_format,
        )

        if isinstance(input_text, str):
            return completion.data[0].embedding

        elif isinstance(input_text, list):
            result_emb = [[] for _ in range(len(input_text))]
            for emb in completion.data:
                result_emb[emb.index] = emb.embedding
            return result_emb

        else:
            raise RuntimeError(f"unsupported type={type(input_text)}")

    async def _async_get_embeddings(self, input_text: str | List[str]):
        """
        Get embeddings asynchronously from the OpenAI-compatible API.

        This method implements the abstract _get_embeddings_async method from BaseEmbeddingModel
        by calling the OpenAI-compatible embeddings API asynchronously.

        Args:
            input_text: Single text string or list of text strings to embed

        Returns:
            Embedding vector(s) corresponding to the input text(s)

        Raises:
            RuntimeError: If unsupported input type is provided
        """
        completion = await self._async_client.embeddings.create(
            model=self.model_name,
            input=input_text,
            dimensions=self.dimensions,
            encoding_format=self.encoding_format,
        )

        if isinstance(input_text, str):
            return completion.data[0].embedding

        elif isinstance(input_text, list):
            result_emb = [[] for _ in range(len(input_text))]
            for emb in completion.data:
                result_emb[emb.index] = emb.embedding
            return result_emb

        else:
            raise RuntimeError(f"unsupported type={type(input_text)}")

    def close(self):
        """Close the OpenAI clients and clean up resources."""
        self._client.close()

    async def async_close(self):
        """Asynchronously close the OpenAI clients and clean up resources."""
        await self._async_client.close()
