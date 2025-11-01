import asyncio
import json
import re
from typing import List, Dict

from loguru import logger

from flowllm.context.service_context import C
from flowllm.enumeration.role import Role
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall
from flowllm.utils.common_utils import extract_content


@C.register_op(register_app="FlowLLM")
class CompanyFactorOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(
        self,
        llm: str = "qwen3_max_instruct",
        # llm: str = "qwen3_30b_instruct",
        # llm: str = "qwen3_80b_instruct",
        # llm: str = "qwen25_max_instruct",
        revenue_threshold: float = 0.05,
        profit_threshold: float = 0.05,
        max_segments: int = 3,
        save_answer: bool = True,
        **kwargs,
    ):
        super().__init__(llm=llm, save_answer=save_answer, **kwargs)
        self.revenue_threshold: float = revenue_threshold
        self.profit_threshold: float = profit_threshold
        self.max_segments: int = max_segments

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": "构建公司整体估值的金融因子逻辑图，综合所有业务板块的因子分析",
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

        logger.info(f"开始为公司 {name}({code}) 构建金融因子逻辑图")

        # Step 1: 获取业务板块信息
        segments = await self._get_company_segments(name, code)
        logger.info(f"获取到 {len(segments)} 个业务板块")

        # Step 2: 对每个业务板块调用 CompanySegmentFactorOp
        segment_results = await self._analyze_segments(name, segments)
        logger.info(f"完成 {len(segment_results)} 个业务板块的因子分析")

        # Step 3: 合并所有Meta信息列表
        merged_meta_list = await self._merge_meta_lists(segment_results)
        logger.info(f"合并后的Meta信息数量: {len(merged_meta_list)}")

        # Step 4: 融合所有因子逻辑图
        merged_graph = await self._merge_factor_graphs(name, merged_meta_list, segment_results)
        logger.info(f"完成因子逻辑图融合")

        # Step 5: 清理因子节点中的特殊字符
        cleaned_graph = self._clean_factor_nodes(merged_graph)
        logger.info(f"完成因子节点清理")

        # Step 6: 构建最终结果
        result = {
            "name": name,
            "code": code,
            "segments": [s["name"] for s in segments],
            "meta_list": merged_meta_list,
            "factor_graph": cleaned_graph,
        }

        self.set_result(json.dumps(result, ensure_ascii=False, indent=2))

    async def _get_company_segments(self, name: str, code: str) -> List[Dict]:
        """获取并过滤公司业务板块"""
        from flowllm.op.fin_search.company_operation_op import CompanyOperationOp

        # 调用CompanyOperationOp获取业务板块
        operation_op = CompanyOperationOp()
        await operation_op.async_call(name=name, code=code)

        # 解析返回结果
        operations = json.loads(operation_op.output)
        logger.info(f"原始业务板块: {operations}")

        # 过滤营收和利润都低于阈值的板块
        filtered_segments = []
        for op in operations:
            revenue = op.get("revenue")
            profit = op.get("profit")

            # 至少有一个指标超过阈值，或者至少有一个指标有值
            keep = False
            if revenue is not None and revenue >= self.revenue_threshold:
                keep = True
            if profit is not None and profit >= self.profit_threshold:
                keep = True
            # 如果revenue或profit为null，但另一个有值，也保留
            if (revenue is None and profit is not None) or (profit is None and revenue is not None):
                keep = True

            if keep:
                filtered_segments.append(op)

        # 按重要性排序（优先revenue，其次profit）
        def sort_key(seg):
            r = seg.get("revenue") or 0
            p = seg.get("profit") or 0
            return -(r + p)  # 降序

        filtered_segments.sort(key=sort_key)

        # 最多保留max_segments个板块
        result = filtered_segments[: self.max_segments]
        logger.info(f"过滤后保留 {len(result)} 个业务板块: {[s['name'] for s in result]}")

        return result

    async def _analyze_segments(self, name: str, segments: List[Dict]) -> List[Dict]:
        """串行调用CompanySegmentFactorOp分析每个业务板块"""
        from flowllm.op.fin_search.company_segment_factor_op import CompanySegmentFactorOp
        from flowllm.op.search.mcp_search_op import TongyiMcpSearchOp

        logger.info(f"开始串行分析 {len(segments)} 个业务板块")

        results = []
        for i, segment in enumerate(segments):
            segment_name = segment["name"]
            logger.info(f"开始分析业务板块 {i + 1}/{len(segments)}: {segment_name}")

            try:
                # 创建搜索Op和因子分析Op
                search_op = TongyiMcpSearchOp()
                factor_op = CompanySegmentFactorOp() << search_op

                # 串行执行任务
                await factor_op.async_call(name=name, segment=segment_name)

                # 解析返回结果（包含meta_list和mermaid_graph）
                factor_result = json.loads(factor_op.output)

                result = {
                    "segment": segment["name"],
                    "revenue": segment.get("revenue"),
                    "profit": segment.get("profit"),
                    "mermaid_graph": factor_result["mermaid_graph"],
                    "meta_list": factor_result["meta_list"],
                }

                results.append(result)
                logger.info(f"板块 {segment_name} 分析成功")

            except Exception as e:
                logger.exception(f"板块 {segment_name} 分析失败: {e}")
                continue

        logger.info(f"完成 {len(results)}/{len(segments)} 个板块的分析")
        return results

    async def _merge_meta_lists(self, segment_results: List[Dict]) -> List[str]:
        """合并并去重所有业务板块的Meta信息列表"""
        # 收集所有meta信息
        all_meta = []
        for result in segment_results:
            all_meta.extend(result.get("meta_list", []))

        if not all_meta:
            logger.warning("没有收集到任何Meta信息")
            return []

        # 使用LLM进行合并去重和冲突解决
        prompt = self.prompt_format(
            prompt_name="merge_meta_prompt",
            meta_lists=json.dumps(all_meta, ensure_ascii=False, indent=2),
        )

        merged_list = await self.llm.achat(
            messages=[Message(role=Role.USER, content=prompt)],
            callback_fn=lambda msg: extract_content(msg.content, "json"),
            enable_stream_print=True,
        )

        return merged_list

    async def _merge_factor_graphs(
        self,
        name: str,
        meta_list: List[str],
        segment_results: List[Dict],
    ) -> str:
        """融合所有业务板块的因子逻辑图"""
        # 收集所有segment的mermaid图
        segment_graphs = []
        for result in segment_results:
            segment_graphs.append(
                {
                    "segment": result["segment"],
                    "graph": result["mermaid_graph"],
                }
            )

        # 使用LLM融合所有图
        prompt = self.prompt_format(
            prompt_name="merge_graphs_prompt",
            name=name,
            meta_list=json.dumps(meta_list, ensure_ascii=False, indent=2),
            segment_graphs=json.dumps(segment_graphs, ensure_ascii=False, indent=2),
        )

        merged_graph = await self.llm.achat(
            messages=[Message(role=Role.USER, content=prompt)],
            callback_fn=lambda msg: extract_content(msg.content, "mermaid"),
            enable_stream_print=True,
        )

        return merged_graph

    def _clean_factor_nodes(self, mermaid_graph: str) -> str:
        """清理mermaid图中因子节点的特殊字符

        查找所有形如 Ax[yyyy] 的因子节点，确保 yyyy 中不包含小括号、花括号、方括号
        """

        def clean_content(match):
            node_id = match.group(1)  # Ax
            content = match.group(2)  # yyyy

            # 移除所有括号：() {} []
            cleaned_content = content.replace("(", "").replace(")", "")
            cleaned_content = cleaned_content.replace("{", "").replace("}", "")
            cleaned_content = cleaned_content.replace("[", "").replace("]", "")

            # 如果内容发生了变化，记录日志
            if content != cleaned_content:
                logger.debug(f"清理因子节点: {node_id}[{content}] -> {node_id}[{cleaned_content}]")

            return f"{node_id}[{cleaned_content}]"

        # 匹配 Ax[...] 格式的因子节点（A后跟数字，方括号内是内容）
        # 使用非贪婪匹配，确保匹配到最近的右方括号
        pattern = r"(A\d+)\[([^\]]+)\]"

        cleaned_graph = re.sub(pattern, clean_content, mermaid_graph)

        return cleaned_graph


async def main():
    from flowllm.app import FlowLLMApp

    async with FlowLLMApp(args=["config=fin_research"]):
        test_cases = [
            ("紫金矿业", "601899"),
            # ("川投能源", "600674"),
            # ("兴业银锡", "000426"),
            # ("小米集团", "01810"),
            # ("阿里巴巴", "09988"),
        ]

        for name, code in test_cases:
            logger.info(f"\n{'=' * 60}\n测试: {name}({code})\n{'=' * 60}")
            op = CompanyFactorOp()
            await op.async_call(name=name, code=code)
            logger.info(f"\n最终结果:\n{op.output}")


if __name__ == "__main__":
    asyncio.run(main())
