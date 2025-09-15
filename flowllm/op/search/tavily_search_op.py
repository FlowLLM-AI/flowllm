import asyncio
import json
import os
from functools import partial
from typing import Union, List

from loguru import logger
from tavily import TavilyClient

from flowllm.context import FlowContext, C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class TavilySearchOp(BaseAsyncToolOp):
    def __init__(self,
                 max_retries: int = 3,
                 raise_exception: bool = False,
                 item_max_count: int = 20000,
                 all_max_count: int = 50000,
                 **kwargs):
        super().__init__(max_retries=max_retries, raise_exception=raise_exception, **kwargs)

        self._client: TavilyClient | None = None
        self.item_max_count: int = item_max_count
        self.all_max_count: int = all_max_count

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "web_search",
            "description": "Use search keywords to retrieve relevant information from the internet. If there are multiple search keywords, please use each keyword separately to call this tool.",
            "input_schema": {
                "query": {
                    "type": "string",
                    "description": "search keyword",
                    "required": True
                }
            },
            "output_schema": {
                "tavily_search_result": {
                    "type": "string",
                    "description": "web search result",
                }
            }
        })

    @property
    def client(self):
        if self._client is None:
            self._client = TavilyClient(api_key=os.environ["FLOW_TAVILY_API_KEY"])
        return self._client

    async def search(self, query: str):
        loop = asyncio.get_event_loop()
        func = partial(self.client.search, query=query)
        task = loop.run_in_executor(executor=C.thread_pool, func=func)  # noqa
        return await task

    async def extract(self, urls: Union[List[str], str]):
        loop = asyncio.get_event_loop()
        func = partial(self.client.extract, urls=urls, format="text")
        task = loop.run_in_executor(executor=C.thread_pool, func=func)  # noqa
        return await task

    async def async_execute(self):
        query: str = self.input_dict["query"]
        logger.info(f"tavily.query: {query}")

        if self.enable_cache:
            cached_result = self.cache.load(query)
            if cached_result:
                self.set_result(json.dumps(cached_result, ensure_ascii=False, indent=2))
                return

        response = await self.search(query=query)
        logger.info(f"tavily.response: {response}")

        url_info_dict = {item["url"]: item for item in response["results"]}
        response_extract = await self.extract(urls=[item["url"] for item in response["results"]])
        logger.info(f"tavily.response_extract: {response_extract}")

        final_result = {}
        all_char_count = 0
        for item in response_extract["results"]:
            url = item["url"]
            raw_content: str = item["raw_content"]
            if len(raw_content) > self.item_max_count:
                raw_content = raw_content[:self.item_max_count]
            if all_char_count + len(raw_content) > self.all_max_count:
                raw_content = raw_content[:self.all_max_count - all_char_count]

            if raw_content:
                final_result[url] = url_info_dict[url]
                final_result[url]["raw_content"] = raw_content
                all_char_count += len(raw_content)

        if not final_result:
            raise RuntimeError("tavily return empty result")

        if self.enable_cache and final_result:
            self.cache.save(query, final_result, expire_hours=self.cache_expire_hours)

        self.set_result(json.dumps(final_result, ensure_ascii=False, indent=2))

async def async_main():
    op = TavilySearchOp()
    context = FlowContext(query="紫金怎么样？雪球")
    await op.async_call(context=context)
    print(context.tavily_search_result)


if __name__ == "__main__":
    asyncio.run(async_main())
