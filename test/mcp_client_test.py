import json

from fastmcp import Client
from mcp.types import CallToolResult


async def main():
    async with Client("http://0.0.0.0:8001/sse/") as client:

        tools = await client.list_tools()
        for tool in tools:
            print(tool.model_dump_json())

            result: CallToolResult = await client.call_tool(tool.name, arguments={"a": 2, "b": 3})
            print(result.content)
            print(result.structured_content)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
