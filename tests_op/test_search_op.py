"""Test module for search operations.

This module provides test functions for various search operations including
Tongyi MCP search, BochaAI MCP search, and Tavily search.
"""

import asyncio

from flowllm.main import FlowLLMApp


async def main():
    """Test function for various search operations.

    This function tests different search operations by executing sample queries
    and printing the results for Tongyi MCP search, BochaAI MCP search, and Tavily search.
    """
    async with FlowLLMApp("config=search"):
        query = "what is ai?"

        from flowllm.gallery.search import TongyiMcpSearchOp

        op = TongyiMcpSearchOp()
        await op.async_call(query=query)
        print("tongyi:", op.output)

        from flowllm.gallery.search import BochaMcpSearchOp

        op = BochaMcpSearchOp()
        await op.async_call(query=query)
        print("bocha:", op.output)

        from flowllm.gallery.search import TavilySearchOp

        op = TavilySearchOp()
        await op.async_call(query=query)
        print("tavily:", op.output)


if __name__ == "__main__":
    asyncio.run(main())
