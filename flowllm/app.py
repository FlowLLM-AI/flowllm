import asyncio
import json

from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.tools import FunctionTool

from flowllm.op.akshare.akshare_op import AkshareDataOp
from flowllm.utils.common_utils import load_env

load_env()

mcp = FastMCP("flowllm")
op = AkshareDataOp()

tools = [
    FunctionTool.from_function(fn=op.parse_query,
                               name="get_stock_name_and_code_by_query",
                               description="可以根据用户问题提取对应的A股股票名称和股票代码"),

    FunctionTool.from_function(fn=op.get_code_infos,
                               name="get_code_infos",
                               description="可以根据A股的股票代码获取公司的对应信息"),

    FunctionTool.from_function(fn=op.get_code_infos,
                               name="get_code_infos",
                               description="可以根据A股的股票代码获取公司的对应信息"),

    FunctionTool.from_function(fn=op.get_code_current_info,
                               name="get_code_current_info",
                               description="""可以根据A股的股票代码获取公司的当前信息，包括："
最新价	float64	-
涨跌幅	float64	注意单位: %
涨跌额	float64	-
成交量	float64	注意单位: 手
成交额	float64	注意单位: 元
振幅	float64	注意单位: %
最高	float64	-
最低	float64	-
今开	float64	-
昨收	float64	-
量比	float64	-
换手率	float64	注意单位: %
市盈率-动态	float64	-
市净率	float64	-
总市值	float64	注意单位: 元
流通市值	float64	注意单位: 元
涨速	float64	-
5分钟涨跌	float64	注意单位: %
60日涨跌幅	float64	注意单位: %
年初至今涨跌幅	float64	注意单位: %
"""),
    FunctionTool.from_function(fn=op.get_code_flow,
                               name="get_code_flow",
                               description="可以根据A股的股票代码获取资金的流入流出情况"),
    FunctionTool.from_function(fn=op.get_code_basic_financial,
                               name="get_code_basic_financial",
                               description="可以根据A股的股票代码获取公司最新的财务情况"),
    FunctionTool.from_function(fn=op.get_code_news,
                               name="get_code_news",
                               description="可以根据A股的股票代码获取公司最新的新闻，注意新闻的生效时间"),
]

for tool in tools:
    mcp.add_tool(tool)


# def main():
#     mcp.run()
#     # mcp.run(transport="sse", port=8001, host="0.0.0.0")
#
#
# if __name__ == "__main__":
#     main()


async def main():
    """Example usage of MCPClient"""
    async with Client(mcp) as client:
        # List available tools
        tools: list[Tool] = await client.list_tools()
        print("Available tools:")
        for t in tools:
            print(t.model_dump_json(indent=2))

        result1 = await client.call_tool("get_stock_name_and_code_by_query", arguments={"query":"帮我分析一下阿里巴巴"})
        result2 = await client.call_tool("get_code_infos", arguments={"code":"000001"})
        result3 = await client.call_tool("get_code_current_info", arguments={"code": "000001"})
        result4 = await client.call_tool("get_code_flow", arguments={"code": "000001"})
        result5 = await client.call_tool("get_code_basic_financial", arguments={"code": "000001"})
        result6 = await client.call_tool("get_code_news", arguments={"code": "000001"})

        print(json.dumps(json.loads(result1.content[0].text), indent=2, ensure_ascii=False))
        print(json.dumps(json.loads(result2.content[0].text), indent=2, ensure_ascii=False))
        print(json.dumps(json.loads(result3.content[0].text), indent=2, ensure_ascii=False))
        print(json.dumps(json.loads(result4.content[0].text), indent=2, ensure_ascii=False))
        print(json.dumps(json.loads(result5.content[0].text), indent=2, ensure_ascii=False))
        print(json.dumps(json.loads(result6.content[0].text), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
