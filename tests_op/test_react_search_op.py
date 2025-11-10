"""Test script for ReactSearchOp.

This script provides test cases for ReactSearchOp class.
It can be run directly with: python test_react_search_op.py
"""

import asyncio

from flowllm.gallery.react_search_op import ReactSearchOp
from flowllm.main import FlowLLMApp


async def async_main():
    """Test function for ReactSearchOp."""
    async with FlowLLMApp():
        op = ReactSearchOp()
        await op.async_call(query="茅台和五粮现在股价多少？")
        print(op.output)


if __name__ == "__main__":
    asyncio.run(async_main())
