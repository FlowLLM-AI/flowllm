"""Test script for DashscopeSearchOp.

This script provides test cases for DashscopeSearchOp class.
It can be run directly with: python test_dashscope_search_op.py
"""

import asyncio

from flowllm.gallery.dashscope_search_op import DashscopeSearchOp
from flowllm.main import FlowLLMApp


async def async_main():
    """Test function for DashscopeSearchOp."""
    async with FlowLLMApp():
        op = DashscopeSearchOp(model="qwen3-max", enable_role_prompt=True)
        await op.async_call(query="藏格矿业的业务主要有哪几块？营收和利润的角度分析 雪球")
        print(op.output)


if __name__ == "__main__":
    asyncio.run(async_main())
