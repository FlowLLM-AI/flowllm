import os
from typing import Literal, List

from openai import OpenAI, AsyncOpenAI
from pydantic import Field, PrivateAttr, model_validator

from flowllm.context.service_context import C
from flowllm.embedding_model.base_embedding_model import BaseEmbeddingModel


@C.register_embedding_model("openai_compatible")
class OpenAICompatibleEmbeddingModel(BaseEmbeddingModel):
    """
    OpenAI-compatible embedding model implementation.
    
    This class provides an implementation of BaseEmbeddingModel that works with
    OpenAI-compatible embedding APIs, including OpenAI's official API and
    other services that follow the same interface.
    """
    # API configuration fields
    api_key: str = Field(default_factory=lambda: os.getenv("FLOW_EMBEDDING_API_KEY"),
                         description="API key for authentication")
    base_url: str = Field(default_factory=lambda: os.getenv("FLOW_EMBEDDING_BASE_URL"),
                          description="Base URL for the API endpoint")
    model_name: str = Field(default="", description="Name of the embedding model to use")
    dimensions: int = Field(default=1024, description="Dimensionality of the embedding vectors")
    encoding_format: Literal["float", "base64"] = Field(default="float", description="Encoding format for embeddings")

    # Private OpenAI client instances
    _client: OpenAI = PrivateAttr()
    _async_client: AsyncOpenAI = PrivateAttr()

    @model_validator(mode="after")
    def init_client(self):
        """
        Initialize the OpenAI clients after model validation.
        
        This method is called automatically after Pydantic model validation
        to set up both sync and async OpenAI clients with the provided API key and base URL.
        
        Returns:
            self: The model instance for method chaining
        """
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self._async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        return self

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
            encoding_format=self.encoding_format)

        if isinstance(input_text, str):
            return completion.data[0].embedding

        elif isinstance(input_text, list):
            result_emb = [[] for _ in range(len(input_text))]
            for emb in completion.data:
                result_emb[emb.index] = emb.embedding
            return result_emb

        else:
            raise RuntimeError(f"unsupported type={type(input_text)}")

    async def _get_embeddings_async(self, input_text: str | List[str]):
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
            encoding_format=self.encoding_format
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


def main():
    from flowllm.utils.common_utils import load_env

    load_env()
    model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    res1 = model.get_embeddings(
        "The clothes are of good quality and look good, definitely worth the wait. I love them.")
    res2 = model.get_embeddings(["aa", "bb"])
    print(res1)
    print(res2)


async def async_main():
    from flowllm.utils.common_utils import load_env

    load_env()
    model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")

    # Test async single text embedding
    res1 = await model.get_embeddings_async(
        "The clothes are of good quality and look good, definitely worth the wait. I love them.")

    # Test async batch text embedding
    res2 = await model.get_embeddings_async(["aa", "bb"])

    print("Async results:")
    print(res1)
    print(res2)


if __name__ == "__main__":
    # main()
    import asyncio

    asyncio.run(async_main())
