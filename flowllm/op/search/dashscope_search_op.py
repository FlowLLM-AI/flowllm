import os
import time
from typing import Dict, Any, List

import dashscope
from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_llm_op import BaseLLMOp
from flowllm.storage.cache.data_cache import DataCache


@C.register_op()
class DashscopeSearchOp(BaseLLMOp):
    file_path: str = __file__

    """
    Dashscope search operation using Alibaba's Qwen model with search capabilities.

    This operation performs web search using Dashscope's Generation API with search enabled.
    It extracts search results and provides formatted responses with citations.
    """

    def __init__(self,
                 model: str = "qwen-plus",
                 enable_print: bool = True,
                 enable_cache: bool = False,
                 cache_path: str = "./dashscope_search_cache",
                 cache_expire_hours: float = 0.1,
                 max_retries: int = 3,
                 search_strategy: str = "max",
                 return_only_content: bool = True,
                 enable_role_prompt: bool = True,
                 **kwargs):
        super().__init__(**kwargs)

        self.model = model
        self.enable_print = enable_print
        self.enable_cache = enable_cache
        self.cache_expire_hours = cache_expire_hours
        self.max_retries = max_retries
        self.search_strategy = search_strategy
        self.return_only_content = return_only_content
        self.enable_role_prompt = enable_role_prompt

        # Ensure API key is available
        self.api_key = os.environ["FLOW_DASHSCOPE_API_KEY"]
        self.cache_path: str = cache_path
        self._cache: DataCache | None = None

    @property
    def cache(self):
        if self.enable_cache and self._cache is None:
            self._cache = DataCache(self.cache_path)
        return self._cache

    @staticmethod
    def format_search_results(search_results: List[Dict[str, Any]]) -> str:
        """Format search results for display"""
        formatted_results = ["=" * 20 + " Search Results " + "=" * 20]

        for web in search_results:
            formatted_results.append(f"[{web['index']}]: [{web['title']}]({web['url']})")

        return "\n".join(formatted_results)

    def post_process(self, response_data: dict) -> dict:
        """Post-process the response and optionally print results"""
        if self.enable_print:
            # Print search information
            if "search_results" in response_data:
                search_info = self.format_search_results(response_data["search_results"])
                logger.info(f"Search Information:\n{search_info}")

            # Print response content
            if "response_content" in response_data:
                logger.info("=" * 20 + " Response Content " + "=" * 20)
                logger.info(response_data["response_content"])

        return response_data

    def execute(self):
        """Execute the Dashscope search operation"""
        # Get query from context - support multiple parameter names
        query = self.context.query

        # Check cache first
        if self.enable_cache and self.cache:
            cached_result = self.cache.load(query)
            if cached_result:
                result = self.post_process(cached_result)
                if self.return_only_content:
                    self.context.dashscope_search_result = result["response_content"]
                else:
                    self.context.dashscope_search_result = result

                return

        if self.enable_role_prompt:
            user_query = self.prompt_format(prompt_name="role_prompt", query=query)
        else:
            user_query = query
        messages: list = [{"role": "user", "content": user_query}]

        # Retry logic for API calls
        for attempt in range(self.max_retries):
            try:
                # Call Dashscope Generation API with search enabled
                response = dashscope.Generation.call(
                    api_key=self.api_key,
                    model=self.model,
                    messages=messages,
                    enable_search=True,  # Enable web search
                    search_options={
                        "forced_search": True,  # Force web search
                        "enable_source": True,  # Include search source information
                        "enable_citation": False,  # Enable citation markers
                        "search_strategy": self.search_strategy,  # Search strategy
                    },
                    result_format="message",
                )

                # Extract search results and response content
                search_results = []
                response_content = ""

                if hasattr(response, 'output') and response.output:
                    # Extract search information
                    if hasattr(response.output, 'search_info') and response.output.search_info:
                        search_results = response.output.search_info.get("search_results", [])

                    # Extract response content
                    if (hasattr(response.output, 'choices') and
                            response.output.choices and
                            len(response.output.choices) > 0):
                        response_content = response.output.choices[0].message.content

                # Prepare final result
                final_result = {
                    "query": query,
                    "search_results": search_results,
                    "response_content": response_content,
                    "model": self.model,
                    "search_strategy": self.search_strategy
                }

                # Cache the result if enabled
                if self.enable_cache and self.cache:
                    self.cache.save(query, final_result, expire_hours=self.cache_expire_hours)

                # Post-process and set context
                result = self.post_process(final_result)
                if self.return_only_content:
                    self.context.dashscope_search_result = result["response_content"]
                else:
                    self.context.dashscope_search_result = result

                return

            except Exception as e:
                logger.warning(f"Dashscope search attempt {attempt + 1} failed for query='{query}': {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(attempt + 1)  # Exponential backoff
                else:
                    logger.error(f"All {self.max_retries} attempts failed for Dashscope search")

        self.context.dashscope_search_result = "dashscope_search failed"


def main():
    from flowllm.utils.common_utils import load_env

    load_env()

    C.set_default_service_config().init_by_service_config()

    op = DashscopeSearchOp(enable_print=True, enable_cache=False)

    context = FlowContext(query="杭州明天天气")
    op(context=context)
    print(context.dashscope_search_result)


if __name__ == "__main__":
    main()
