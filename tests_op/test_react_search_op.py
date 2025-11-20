"""Test script for ReactSearchOp.

This script provides test cases for ReactSearchOp class.
It can be run directly with: python test_react_search_op.py
"""

import asyncio

from flowllm.gallery.agent import ReactSearchOp
from flowllm.main import FlowLLMApp


async def async_main():
    """Test function for ReactSearchOp."""
    async with FlowLLMApp():
        op = ReactSearchOp(add_think_tool=True, language="zh")
        await op.async_call(query="小米股价为什么一直跌？现在还值得买吗？")
        print(op.output)


if __name__ == "__main__":
    asyncio.run(async_main())
