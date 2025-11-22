"""Mock search operation that uses LLM to generate search results."""

import json
import random

from loguru import logger

from ...core.context import C
from ...core.enumeration import Role
from ...core.op import BaseAsyncOp
from ...core.schema import Message
from ...core.utils import extract_content


@C.register_op()
class MockSearchOp(BaseAsyncOp):
    """Mock search operation that uses LLM to generate realistic search results.

    This operation takes a search query and uses an LLM to generate 0-5 mock
    search results. Each result contains snippet, title, url, hostname, and hostlogo.
    """

    file_path: str = __file__

    def __init__(
        self,
        llm: str = "qwen3_30b_instruct",
        **kwargs,
    ):
        """Initialize the MockSearchOp.

        Args:
            llm: Name of the LLM to use for generating search results.
            **kwargs: Additional arguments passed to BaseAsyncToolOp.
        """
        super().__init__(llm=llm, **kwargs)

    async def async_execute(self):
        """Execute the mock search operation.

        Uses LLM to generate realistic search results based on the query.
        Results are randomly generated between 0-5 items.
        """
        query = self.context.query
        if not query:
            logger.warning(f"{self.name}: query is empty")
            self.context.response.answer = "No results found."
            return

        num_results = random.randint(0, 5)
        user_prompt = self.prompt_format("mock_search_op_prompt", query=query, num_results=num_results)

        messages = [
            Message(
                role=Role.SYSTEM,
                content="You are a helpful assistant that generates realistic search results in JSON format.",
            ),
            Message(role=Role.USER, content=user_prompt),
        ]

        logger.info(f"{self.name}: Generating {num_results} results for query: {query}")

        def callback_fn(message: Message):
            return extract_content(message.content, "json")

        search_results: str = await self.llm.achat(messages=messages, callback_fn=callback_fn)
        self.context.response.answer = json.dumps(search_results, ensure_ascii=False, indent=2)
