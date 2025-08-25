import json
import os
import time
from typing import Literal

from loguru import logger
from tavily import TavilyClient

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_op import BaseOp
from flowllm.storage.cache.data_cache import DataCache


@C.register_op()
class TavilySearchOp(BaseOp):
    def __init__(self,
                 enable_print: bool = True,
                 enable_cache: bool = False,
                 cache_path: str = "./web_search_cache",
                 cache_expire_hours: float = 0.1,
                 topic: Literal["general", "news", "finance"] = "general",
                 max_retries: int = 3,
                 return_only_content: bool = True,
                 **kwargs):
        super().__init__(**kwargs)

        self.enable_print = enable_print
        self.enable_cache = enable_cache
        self.cache_expire_hours = cache_expire_hours
        self.topic = topic
        self.max_retries = max_retries
        self.return_only_content = return_only_content

        # Initialize DataCache if caching is enabled
        self.cache = DataCache(cache_path) if self.enable_cache else None
        self._client = TavilyClient(api_key=os.getenv("FLOW_TAVILY_API_KEY", ""))

    def post_process(self, response):
        if self.enable_print:
            logger.info("response=\n" + json.dumps(response, indent=2, ensure_ascii=False))

        return response

    def execute(self):
        # Get query from context
        query: str = self.context.query

        # Check cache first
        if self.enable_cache and self.cache:
            cached_result = self.cache.load(query)
            if cached_result:
                final_result = self.post_process(cached_result)
                if self.return_only_content:
                    self.context.tavily_search_result = json.dumps(final_result, ensure_ascii=False, indent=2)
                else:
                    self.context.tavily_search_result = final_result
                return

        for i in range(self.max_retries):
            try:
                response = self._client.search(query=query, topic=self.topic)
                url_info_dict = {item["url"]: item for item in response["results"]}
                response_extract = self._client.extract(urls=[item["url"] for item in response["results"]],
                                                        format="text")

                final_result = {}
                for item in response_extract["results"]:
                    url = item["url"]
                    final_result[url] = url_info_dict[url]
                    final_result[url]["raw_content"] = item["raw_content"]

                # Cache the result if enabled
                if self.enable_cache and self.cache:
                    self.cache.save(query, final_result, expire_hours=self.cache_expire_hours)

                final_result = self.post_process(final_result)

                if self.return_only_content:
                    self.context.tavily_search_result = json.dumps(final_result, ensure_ascii=False, indent=2)
                else:
                    self.context.tavily_search_result = final_result
                return

            except Exception as e:
                logger.exception(f"tavily search with query={query} encounter error with e={e.args}")
                time.sleep(i + 1)

        self.context.tavily_search_result = "tavily search failed!"


if __name__ == "__main__":
    from flowllm.utils.common_utils import load_env

    load_env()

    C.set_default_service_config().init_by_service_config()

    op = TavilySearchOp(enable_cache=True)
    context = FlowContext(query="A股医药为什么一直涨")
    op(context=context)
    print(context.tavily_search_result)
