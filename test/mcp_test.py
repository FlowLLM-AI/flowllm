import asyncio
import json
from typing import List

from fastmcp import Client, FastMCP
from pydantic import BaseModel, Field

async def main():
    """Example usage of MCPClient"""
    async with Client("flowllm_fin") as client:
        # List available tools
        tools = await client.list_tools()
        print("Available tools:", json.dumps(tools, ensure_ascii=False, indent=2))



if __name__ == "__main__":
    import akshare as ak

    stock_sh_a_spot_em_df = ak.stock_sh_a_spot_em()
    print(stock_sh_a_spot_em_df)
