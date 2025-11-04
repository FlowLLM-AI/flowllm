"""Test script for ExecuteCodeOp.

This script moves the inline main tests from gallery/execute_code_op.py
into the tests directory so they can be executed independently.
"""

import asyncio

from flowllm.gallery.execute_code_op import ExecuteCodeOp
from flowllm.main import FlowLLMApp

async def async_main():
    async with FlowLLMApp():
        op = ExecuteCodeOp()
        print(op.tool_call.model_dump_json(exclude_none=True))
        print(op.tool_call.simple_input_dump())
        print(op.tool_call.simple_output_dump())

        await op.async_call(code="print('Hello World')")
        print(op.output)

        await op.async_call(code="print('Hello World!'")
        print(op.output)


if __name__ == "__main__":
    asyncio.run(async_main())
