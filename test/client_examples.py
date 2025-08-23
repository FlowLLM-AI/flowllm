"""
Example usage of FlowLLM service clients
"""
import asyncio
import json

from flowllm.client import HttpClient, AsyncHttpClient, MCPClient, SyncMCPClient


def http_client_example():
    """Example of using synchronous HTTP client"""
    print("=== HTTP Client Example (Sync) ===")

    with HttpClient(base_url="http://localhost:8001") as client:
        health = client.health_check()
        print(f"Service health: {health}")

        result = client.execute_tool_flow(flow_name="get_a_stock_infos", query="茅台怎么样？")
        print(f"Flow result: {result.answer}")

        result = client.list_tool_flows()
        print(json.dumps(result, ensure_ascii=False))

async def async_http_client_example():
    """Example of using asynchronous HTTP client"""
    print("\n=== HTTP Client Example (Async) ===")

    async with AsyncHttpClient(base_url="http://localhost:8001") as client:
        health = await client.health_check()
        print(f"Service health: {health}")

        result = await client.execute_tool_flow(flow_name="get_a_stock_infos", query="茅台怎么样？")
        print(f"Flow result: {result.answer}")

        result = await client.list_tool_flows()
        print(json.dumps(result, ensure_ascii=False))



async def mcp_client_example():
    print("\n=== MCP Client Example (Async) ===")

    async with MCPClient(transport="sse", host="0.0.0.0", port=8001) as client:
        tools = await client.list_tools()
        for tool in tools:
            print(tool.model_dump_json())

        if tools:
            result = await client.call_tool(tool_name=tools[0].name, arguments={"query": "茅台怎么样？"})
            print(f"tool result: {result}")


def sync_mcp_client_example():
    """Example of using synchronous MCP client"""
    print("\n=== MCP Client Example (Sync) ===")

    with SyncMCPClient(transport="sse", host="0.0.0.0", port=8001) as client:
        # List available tools
        tools = client.list_tools()
        for tool in tools:
            print(tool.model_dump_json())

        if tools:
            result = client.call_tool(tool_name=tools[0].name, arguments={"query": "茅台怎么样？"})
            print(f"tool result: {result}")


async def main():
    await async_http_client_example()
    # await mcp_client_example()


def main_sync():
    http_client_example()
    # sync_mcp_client_example()


if __name__ == "__main__":
    # asyncio.run(main())
    main_sync()
