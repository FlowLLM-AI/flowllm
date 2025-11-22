"""Tavily web search operation module.

This module provides a tool operation for performing web searches using the Tavily API.
It enables LLM models to retrieve relevant information from the internet by executing
search queries and optionally extracting content from search results.
"""

import json
import os
from typing import TYPE_CHECKING

from loguru import logger

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall

if TYPE_CHECKING:
    from tavily import AsyncTavilyClient


@C.register_op()
class TavilySearchOp(BaseAsyncToolOp):
    """A tool operation for performing web searches using Tavily API.

    This operation enables LLM models to search the internet for information by
    providing search keywords. It supports optional content extraction from search
    results with configurable character limits.

    Attributes:
        enable_extract: Whether to extract raw content from search results (default: False).
        item_max_char_count: Maximum character count per item when extracting (default: 20000).
        all_max_char_count: Maximum total character count for all extracted items (default: 50000).
    """

    def __init__(
        self,
        enable_extract: bool = False,
        item_max_char_count: int = 20000,
        all_max_char_count: int = 50000,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.enable_extract: bool = enable_extract
        self.item_max_char_count: int = item_max_char_count
        self.all_max_char_count: int = all_max_char_count

        self._client: AsyncTavilyClient | None = None

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": "Use search keywords to retrieve relevant information from the internet.",
                "input_schema": {
                    "query": {
                        "type": "string",
                        "description": "search keyword",
                        "required": True,
                    },
                },
            },
        )

    @property
    def client(self):
        """Get or create the Tavily async client instance.

        Returns:
            AsyncTavilyClient: The Tavily async client instance.
        """
        if self._client is None:
            from tavily import AsyncTavilyClient

            self._client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        return self._client

    async def async_execute(self):
        query: str = self.input_dict["query"]
        logger.info(f"tavily.query: {query}")

        if self.enable_cache:
            cached_result = self.cache.load(query)
            if cached_result:
                self.set_output(json.dumps(cached_result, ensure_ascii=False, indent=2))
                return

        response = await self.client.search(query=query)
        logger.info(f"tavily.response: {response}")

        if not self.enable_extract:
            # 如果不需要 extract，直接返回 search 的结果
            if not response.get("results"):
                raise RuntimeError("tavily return empty result")

            final_result = {item["url"]: item for item in response["results"]}

            if self.enable_cache and final_result:
                self.cache.save(query, final_result, expire_hours=self.cache_expire_hours)

            self.set_output(json.dumps(final_result, ensure_ascii=False, indent=2))
            return

        # enable_extract=True 时的原有逻辑
        url_info_dict = {item["url"]: item for item in response["results"]}
        response_extract = await self.client.extract(urls=[item["url"] for item in response["results"]])
        logger.info(f"tavily.response_extract: {response_extract}")

        final_result = {}
        all_char_count = 0
        for item in response_extract["results"]:
            url = item["url"]
            raw_content: str = item["raw_content"]
            if len(raw_content) > self.item_max_char_count:
                raw_content = raw_content[: self.item_max_char_count]
            if all_char_count + len(raw_content) > self.all_max_char_count:
                raw_content = raw_content[: self.all_max_char_count - all_char_count]

            if raw_content:
                final_result[url] = url_info_dict[url]
                final_result[url]["raw_content"] = raw_content
                all_char_count += len(raw_content)

        if not final_result:
            raise RuntimeError("tavily return empty result")

        if self.enable_cache and final_result:
            self.cache.save(query, final_result, expire_hours=self.cache_expire_hours)

        self.set_output(json.dumps(final_result, ensure_ascii=False, indent=2))
