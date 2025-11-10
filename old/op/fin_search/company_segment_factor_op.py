import asyncio
import json
from typing import List

from loguru import logger

from flowllm.context.service_context import C
from flowllm.enumeration.role import Role
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall
from flowllm.utils.common_utils import extract_content, get_datetime


@C.register_op(register_app="FlowLLM")
class CompanySegmentFactorOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(
        self,
        # llm: str = "qwen3_max_instruct",
        llm: str = "qwen3_30b_instruct",
        # llm: str = "qwen3_80b_instruct",
        # llm: str = "qwen25_max_instruct",
        max_steps: int = 5,
        max_search_cnt: int = 3,
        max_approach_cnt: int = 3,
        **kwargs,
    ):
        super().__init__(llm=llm, **kwargs)
        self.max_steps: int = max_steps
        self.max_search_cnt: int = max_search_cnt
        self.max_approach_cnt: int = max_approach_cnt

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": "构建公司某个板块的因子传导路径分析任务，返回Meta信息列表和因子逻辑图",
                "input_schema": {
                    "name": {
                        "type": "string",
                        "description": "公司名称",
                        "required": True,
                    },
                    "segment": {
                        "type": "string",
                        "description": "板块",
                        "required": True,
                    },
                },
            },
        )

    async def async_execute(self):
        name = self.input_dict["name"]
        segment = self.input_dict["segment"]

        # 初始化
        mermaid_graph = self.prompt_format(prompt_name="init_mermaid_graph", name=name, segment=segment)
        meta_list = []
        current_time = get_datetime(time_ft="%Y-%m-%d %H:%M:%S")

        for i in range(self.max_steps):
            logger.info(f"=== Iteration {i+1}/{self.max_steps} ===")

            # Step 1: 生成搜索查询
            search_queries = await self._generate_search_queries(name, segment, meta_list, mermaid_graph)
            if not search_queries:
                logger.info("No more search queries needed, stopping iteration")
                break

            # 执行搜索
            search_content = await self._execute_searches(search_queries)

            # Step 2: 更新Meta信息列表
            meta_list = await self._update_meta_list(name, segment, current_time, search_content, meta_list)

            # Step 3: 更新因子传导图
            mermaid_graph = await self._update_mermaid_graph(name, segment, current_time, meta_list, mermaid_graph)

        # 返回包含meta_list和mermaid_graph的字典
        result = {
            "meta_list": meta_list,
            "mermaid_graph": mermaid_graph,
        }
        self.set_result(json.dumps(result, ensure_ascii=False, indent=2))

    async def _generate_search_queries(self, name: str, segment: str, meta_list: List, mermaid_graph: str) -> List[str]:
        """生成搜索查询列表"""
        prompt = self.prompt_format(
            prompt_name="factor_step1_prompt",
            name=name,
            segment=segment,
            max_search_cnt=self.max_search_cnt,
            meta_list=json.dumps(meta_list, ensure_ascii=False),
            mermaid_graph=mermaid_graph,
        )

        search_list = await self.llm.achat(
            messages=[Message(role=Role.USER, content=prompt)],
            callback_fn=lambda msg: extract_content(msg.content, "json"),
            enable_stream_print=False,
        )

        if search_list and len(search_list) > self.max_search_cnt:
            logger.warning(f"Generated {len(search_list)} queries, truncating to {self.max_search_cnt}")
            search_list = search_list[: self.max_search_cnt]

        logger.info(f"Search queries: {search_list}")
        return search_list or []

    async def _execute_searches(self, search_queries: List[str]) -> str:
        """执行搜索并聚合结果"""
        search_ops: List[BaseAsyncToolOp] = []
        for query in search_queries:
            search_op = self.ops[0].copy()
            assert isinstance(search_op, BaseAsyncToolOp)
            search_ops.append(search_op)
            self.submit_async_task(search_op.async_call, query=query)
            await asyncio.sleep(1)

        await self.join_async_task()

        results = []
        for search_op in search_ops:
            query = search_op.input_dict["query"]
            results.append(f"{query}\n{search_op.output}")

        return "\n\n".join(results)

    async def _update_meta_list(
        self,
        name: str,
        segment: str,
        current_time: str,
        search_content: str,
        meta_list: List,
    ) -> List:
        """更新Meta信息列表"""
        prompt = self.prompt_format(
            prompt_name="factor_step2_prompt",
            name=name,
            segment=segment,
            current_time=current_time,
            search_content=search_content,
            meta_list=json.dumps(meta_list, ensure_ascii=False),
        )

        updated_meta_list = await self.llm.achat(
            messages=[Message(role=Role.USER, content=prompt)],
            callback_fn=lambda msg: extract_content(msg.content, "json"),
            enable_stream_print=False,
        )

        logger.info(f"Updated meta list: {updated_meta_list}")
        return updated_meta_list or meta_list

    async def _update_mermaid_graph(
        self,
        name: str,
        segment: str,
        current_time: str,
        meta_list: List,
        mermaid_graph: str,
    ) -> str:
        """更新因子传导图"""
        prompt = self.prompt_format(
            prompt_name="factor_step3_prompt",
            name=name,
            segment=segment,
            current_time=current_time,
            max_approach_cnt=self.max_approach_cnt,
            meta_list=json.dumps(meta_list, ensure_ascii=False),
            mermaid_graph=mermaid_graph,
        )

        updated_graph = await self.llm.achat(
            messages=[Message(role=Role.USER, content=prompt)],
            callback_fn=lambda msg: extract_content(msg.content, "mermaid"),
            enable_stream_print=False,
        )

        logger.info(f"Updated mermaid graph: {updated_graph}")
        return updated_graph or mermaid_graph


async def main():
    from flowllm.app import FlowLLMApp
    from flowllm.op.search import TongyiMcpSearchOp

    async with FlowLLMApp(args=["config=fin_research"]):
        # name, code, segment = "紫金矿业", "601899", "黄金业务"
        # name, code, segment = "紫金矿业", "601899", "铜业务"
        # name, code, segment = "小米", "01810", "小米汽车"
        name, code, segment = "阿里巴巴", "09988", "AI"
        search_op = TongyiMcpSearchOp()
        op = CompanySegmentFactorOp() << search_op
        await op.async_call(name=name, code=code, segment=segment)
        logger.info(op.output)


if __name__ == "__main__":
    asyncio.run(main())
