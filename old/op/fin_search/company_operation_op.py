import asyncio
import json

from loguru import logger

from flowllm.context.service_context import C
from flowllm.enumeration.role import Role
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.op.crawl.crawl4ai_op import Crawl4aiOp
from flowllm.op.search.mcp_search_op import TongyiMcpSearchOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall
from flowllm.utils.common_utils import extract_content


@C.register_op(register_app="FlowLLM")
class CompanyOperationOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(
        self,
        # llm: str = "qwen3_30b_instruct",
        llm: str = "qwen3_max_instruct",
        min_content_length: int = 5000,
        **kwargs,
    ):
        super().__init__(llm=llm, **kwargs)
        self.min_content_length = min_content_length

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": "获取公司的主营业务信息",
                "input_schema": {
                    "name": {
                        "type": "string",
                        "description": "公司名称",
                        "required": True,
                    },
                    "code": {
                        "type": "string",
                        "description": "股票代码",
                        "required": True,
                    },
                },
            },
        )

    async def async_execute(self):
        name = self.input_dict["name"]
        code = self.input_dict["code"]

        # 爬取同花顺经营分析页面
        crawl_op = Crawl4aiOp()
        await crawl_op.async_call(url=f"https://basic.10jqka.com.cn/{code}/operate.html#stockpage")

        # 判断爬取内容是否充分
        content = crawl_op.output
        if len(content) < self.min_content_length:
            logger.warning(f"爬取内容不足({len(content)}字符)，启用网页搜索补充")

            # 并行搜索营收和利润信息
            ty_op1 = TongyiMcpSearchOp()
            ty_op2 = TongyiMcpSearchOp()

            self.submit_async_task(ty_op1.async_call, query=f"{name} {code} 最新财报 营收占比")
            await asyncio.sleep(1)
            self.submit_async_task(ty_op2.async_call, query=f"{name} {code} 最新财报 利润占比")

            await self.join_async_task()

            content = f"# 网页搜索结果\n\n## 营收信息\n{ty_op1.output}\n\n## 利润信息\n{ty_op2.output}"

        logger.info(f"最终内容长度: {len(content)}字符")

        # 提取业务板块信息
        prompt = self.prompt_format(
            prompt_name="extract_operation_prompt",
            name=name,
            code=code,
            content=content,
        )

        def extract_json_callback(message: Message):
            result = extract_content(message.content, "json")
            if result is None:
                logger.warning("JSON解析失败，返回空列表")
                return []

            if not isinstance(result, list):
                logger.warning(f"返回结果非列表类型: {type(result)}")
                return []

            return result

        operations = await self.llm.achat(
            messages=[Message(role=Role.USER, content=prompt)],
            callback_fn=extract_json_callback,
        )

        logger.info(f"提取业务板块数量: {len(operations)}")
        self.set_result(json.dumps(operations, ensure_ascii=False, indent=2))


async def main():
    from flowllm.app import FlowLLMApp

    async with FlowLLMApp(args=["config=fin_research"]):
        # 测试案例
        test_cases = [
            # ("紫金矿业", "601899"),
            ("小米集团", "01810"),
            # ("阿里巴巴", "09988"),
        ]

        for name, code in test_cases:
            logger.info(f"\n{'=' * 50}\n测试: {name}({code})\n{'=' * 50}")
            op = CompanyOperationOp()
            await op.async_call(code=code, name=name)
            logger.info(f"\n结果:\n{op.output}")


if __name__ == "__main__":
    asyncio.run(main())
