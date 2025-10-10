import asyncio

from loguru import logger

from flowllm import BaseAsyncToolOp
from flowllm.enumeration.role import Role
from flowllm.op.crawl.crawl4ai_op import Crawl4aiOp
from flowllm.op.fin_search.mcp_search_op import TongyiMcpSearchOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall


class CompanyOperationOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(self,
                 llm: str = "qwen3_30b_instruct",
                 # llm: str = "qwen25_max_instruct",
                 **kwargs):
        super().__init__(llm=llm, **kwargs)

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "description": "获取公司的主营业务信息",
            "input_schema": {
                "name": {
                    "type": "string",
                    "description": "公司名称",
                    "required": True
                },
                "code": {
                    "type": "string",
                    "description": "股票代码",
                    "required": True
                }
            }
        })

    async def async_execute(self):
        name = self.input_dict["name"]
        code = self.input_dict["code"]

        crawl_op = Crawl4aiOp()
        await crawl_op.async_call(url=f"https://basic.10jqka.com.cn/{code}/operate.html#stockpage")
        logger.info(f"==========crawl_op.output==========\n{crawl_op.output}")

        if len(crawl_op.output) > 10000:
            content = crawl_op.output
        else:
            ty_op1 = TongyiMcpSearchOp()
            await ty_op1.async_call(query=f"{name} {code} 最新财报 营收占比")
            logger.info(f"==========ty_op1.output==========\n{ty_op1.output}")

            ty_op2 = TongyiMcpSearchOp()
            await ty_op2.async_call(query=f"{name} {code} 最新财报 利润占比")
            logger.info(f"==========ty_op2.output==========\n{ty_op2.output}")

            content = f"网页搜索内容\n{ty_op1.output}\n{ty_op2.output}"

        ths_operation_prompt = self.prompt_format(
            prompt_name="extract_ths_operation_prompt",
            name=name,
            code=code,
            content=content)

        assistant_result = await self.llm.achat(messages=[Message(role=Role.USER, content=ths_operation_prompt)])
        logger.info(assistant_result.content)

        self.set_result("123")


async def main():
    from flowllm.app import FlowLLMApp
    async with FlowLLMApp(args=["config=fin_research"]):
        name, code = "紫金", "601899"
        # name, code = "小米", "01810"
        # name, code = "阿里", "09988"
        # name, code = "藏格", "000408"
        op = CompanyOperationOp()
        await op.async_call(code=code, name=name)
        logger.info(op.output)


if __name__ == "__main__":
    asyncio.run(main())
