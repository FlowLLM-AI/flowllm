import json

from fastmcp import Client


async def main():
    async with Client("http://0.0.0.0:8000/sse/") as client:

        tools = await client.list_tools()
        for tool in tools:
            print(tool.model_dump_json())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
