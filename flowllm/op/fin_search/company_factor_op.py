import asyncio
from typing import List

from loguru import logger

from flowllm import BaseAsyncToolOp
from flowllm.enumeration.role import Role
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall
from flowllm.utils.common_utils import extract_content, get_datetime


class CompanyFactorOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(self,
                 llm: str = "qwen3_30b_instruct",
                 # llm: str = "qwen3_max_instruct",
                 max_steps: int = 5,
                 max_search_cnt: int = 3,
                 **kwargs):
        super().__init__(llm=llm, **kwargs)
        self.max_steps: int = max_steps
        self.max_search_cnt: int = max_search_cnt

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "description": "构建公司某个板块的因子传导路径分析任务",
            "input_schema": {
                "name": {
                    "type": "string",
                    "description": "公司名称",
                    "required": True
                },
                # "code": {
                #     "type": "string",
                #     "description": "股票代码",
                #     "required": True
                # },
                "segment": {
                    "type": "string",
                    "description": "板块",
                    "required": True
                }
            }
        })

    async def async_execute(self):
        name = self.input_dict["name"]
        # code = self.input_dict["code"]
        segment = self.input_dict["segment"]
        init_mermaid_graph = self.prompt_format(prompt_name="init_mermaid_graph", name=name, segment=segment)

        def extract_json(message: Message):
            # logger.info(f"message.content={message.content}")
            return extract_content(message.content, "json")

        def extract_mermaid(message: Message):
            # logger.info(f"message.content={message.content}")
            return extract_content(message.content, "mermaid")

        search_content = ""
        mermaid_graph = init_mermaid_graph

        for i in range(self.max_steps):
            factor_step1_prompt = self.prompt_format(
                prompt_name="factor_step1_prompt",
                name=name,
                segment=segment,
                max_search_cnt=self.max_search_cnt,
                search_content=f"# 搜索内容\n{search_content}" if search_content else "",
                mermaid_graph=mermaid_graph)
            logger.info(f"factor_step1_prompt={factor_step1_prompt}")

            search_list = await self.llm.achat(
                messages=[Message(role=Role.USER, content=factor_step1_prompt)],
                callback_fn=extract_json,
                enable_stream_print=True)

            search_str = "\n".join(search_list)
            logger.info(f"search_str={search_str}")

            if len(search_list) == 0:
                logger.info("find no search query, stop")
                break

            elif len(search_list) > self.max_search_cnt:
                logger.warning(f"search_size={len(search_list)} > max_search_cnt={self.max_search_cnt}")
                search_list = search_list[:self.max_search_cnt]

            search_ops: List[BaseAsyncToolOp] = []
            for search_query in search_list:
                search_op = self.ops[0].copy()
                assert isinstance(search_op, BaseAsyncToolOp)
                search_ops.append(search_op)
                self.submit_async_task(search_op.async_call, query=search_query)
                await asyncio.sleep(1)

            await self.join_async_task()

            search_content = ""
            for search_op in search_ops:
                search_query = search_op.input_dict["query"]
                search_content += search_query + "\n" + search_op.output + "\n\n"
            search_content = search_content.strip()

            factor_step2_prompt = self.prompt_format(
                prompt_name="factor_step2_prompt",
                name=name,
                segment=segment,
                current_time=get_datetime(time_ft="%Y-%m-%d %H:%M:%S"),
                search_content=search_content,
                mermaid_graph=mermaid_graph)
            logger.info(f"factor_step2_prompt={factor_step2_prompt}")

            mermaid_graph = await self.llm.achat(
                messages=[Message(role=Role.USER, content=factor_step2_prompt)],
                callback_fn=extract_mermaid,
                enable_stream_print=True)

            logger.info(f"mermaid_graph={mermaid_graph}")

        self.set_result(mermaid_graph)


async def main():
    from flowllm.app import FlowLLMApp
    from mcp_search_op import TongyiMcpSearchOp
    async with FlowLLMApp(args=["config=fin_research"]):
        name, code, segment = "紫金矿业", "601899", "黄金业务"
        search_op1 = TongyiMcpSearchOp()
        op = CompanyFactorOp() << search_op1
        await op.async_call(name=name, code=code, segment=segment)
        logger.info(op.output)


if __name__ == "__main__":
    asyncio.run(main())
