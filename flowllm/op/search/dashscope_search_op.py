import asyncio
import os
from typing import Dict, Any, List

import dashscope
from loguru import logger

from flowllm.context import FlowContext, C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class DashscopeSearchOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(self,
                 model: str = "qwen-plus",
                 search_strategy: str = "max",
                 enable_role_prompt: bool = True,
                 **kwargs):
        super().__init__(**kwargs)

        self.model: str = model
        self.search_strategy: str = search_strategy
        self.enable_role_prompt: bool = enable_role_prompt

        self.api_key = os.getenv("FLOW_DASHSCOPE_API_KEY", "")

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
                "dashscope_search_result": {
                    "type": "string",
                    "description": "web search result",
                }
            }
        })

    @staticmethod
    def format_search_results(search_results: List[Dict[str, Any]]) -> str:
        """Format search results for display"""
        formatted_results = ["=" * 20 + " Search Results " + "=" * 20]
        for web in search_results:
            formatted_results.append(f"[{web['index']}]: [{web['title']}]({web['url']})")

        return "\n".join(formatted_results)

    async def async_execute(self):
        query: str = self.input_dict["query"]

        if self.enable_cache:
            cached_result = self.cache.load(query)
            if cached_result:
                self.set_result(cached_result["response_content"])
                return

        if self.enable_role_prompt:
            user_query = self.prompt_format(prompt_name="role_prompt", query=query)
        else:
            user_query = query
        logger.info(f"user_query={user_query}")
        messages: list = [{"role": "user", "content": user_query}]

        response = await dashscope.AioGeneration.call(
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

        search_results = []
        response_content = ""

        if hasattr(response, "output") and response.output:
            if hasattr(response.output, "search_info") and response.output.search_info:
                search_results = response.output.search_info.get("search_results", [])

            if hasattr(response.output, "choices") and response.output.choices and len(response.output.choices) > 0:
                response_content = response.output.choices[0].message.content

        final_result = {
            "query": query,
            "search_results": search_results,
            "response_content": response_content,
            "model": self.model,
            "search_strategy": self.search_strategy
        }

        if self.enable_cache:
            self.cache.save(query, final_result, expire_hours=self.cache_expire_hours)

        self.set_result(final_result["response_content"])


async def async_main():
    op = DashscopeSearchOp()
    context = FlowContext(query="what is AI?")
    await op.async_call(context=context)
    print(context.dashscope_search_result)


if __name__ == "__main__":
    asyncio.run(async_main())
