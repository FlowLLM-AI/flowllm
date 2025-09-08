import asyncio
import json
import os
from functools import partial
from typing import Union, List

from tavily import TavilyClient

from flowllm.context import FlowContext, C
from flowllm.op.base_tool_op import BaseToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op()
class TavilySearchOp(BaseToolOp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._client: TavilyClient | None = None

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

        if self.enable_cache:
            cached_result = self.cache.load(query)
            if cached_result:
                self.set_result(json.dumps(cached_result, ensure_ascii=False, indent=2))
                return

        response = await self.search(query=query)
        url_info_dict = {item["url"]: item for item in response["results"]}
        response_extract = await self.extract(urls=[item["url"] for item in response["results"]])

        final_result = {}
        for item in response_extract["results"]:
            url = item["url"]
            final_result[url] = url_info_dict[url]
            final_result[url]["raw_content"] = item["raw_content"]

        if self.enable_cache:
            self.cache.save(query, final_result, expire_hours=self.cache_expire_hours)

        self.set_result(json.dumps(final_result, ensure_ascii=False, indent=2))

async def async_main():
    C.set_service_config().init_by_service_config()

    op = TavilySearchOp()
    context = FlowContext(query="what is AI?")
    await op.async_call(context=context)
    print(context.tavily_search_result)


if __name__ == "__main__":
    asyncio.run(async_main())
