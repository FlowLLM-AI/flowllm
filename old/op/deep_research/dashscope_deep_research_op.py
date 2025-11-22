import asyncio
import os

import dashscope
from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.enumeration.chunk_enum import ChunkEnum
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class DashscopeDeepResearchOp(BaseAsyncToolOp):

    def __init__(self, api_key: str = None, save_answer: bool = True, **kwargs):
        super().__init__(save_answer=save_answer, **kwargs)
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": "Use Dashscope deep research to conduct comprehensive research on a topic",
                "input_schema": {
                    "query": {
                        "type": "string",
                        "description": "research topic or question",
                        "required": True,
                    },
                    "messages": {
                        "type": "array",
                        "description": "conversation messages for context",
                        "required": False,
                    },
                },
            },
        )

    async def async_execute(self):
        if self.input_dict.get("query"):
            query: str = self.input_dict.get("query")
            messages = [{"role": "user", "content": query}]
        elif self.input_dict.get("messages"):
            messages: list = self.input_dict.get("messages")
            query: str = messages[-1].get("content", "")
            messages = [{"role": "user", "content": query}]
        else:
            raise RuntimeError("query or messages is required")

        logger.info(f"Starting deep research with messages={messages}")

        # Step 1: Get initial response (反问阶段)
        await self.context.add_stream_chunk_and_type("正在分析研究主题...\n", ChunkEnum.THINK)

        try:
            responses = await dashscope.AioGeneration.call(
                api_key=self.api_key,
                model="qwen-deep-research",
                messages=messages,
                request_timeout=300000,
                stream=True,
            )

            step1_content = await self._process_responses(responses, "第一步：模型反问确认")
            await self.context.add_stream_chunk_and_type("\n", ChunkEnum.THINK)
            logger.info(f"step1_content={step1_content}")

            # Step 2: Deep research with fixed response
            await self.context.add_stream_chunk_and_type("开始深入研究...\n", ChunkEnum.THINK)

            # Use fixed response for follow-up
            messages.extend(
                [
                    {"role": "assistant", "content": step1_content},
                    {"role": "user", "content": "给我一份带逻辑推理的详细报告"},
                ]
            )

            responses = await dashscope.AioGeneration.call(
                api_key=self.api_key,
                model="qwen-deep-research",
                messages=messages,
                request_timeout=300000,
                stream=True,
            )

            final_content = await self._process_responses(responses, "第二步：深入研究")
            await self.context.add_stream_chunk_and_type("\n", ChunkEnum.ANSWER)
            logger.info(f"final_content={final_content}")

        except Exception as e:
            error_msg = f"Deep research failed: {str(e)}"
            logger.exception(error_msg)
            await self.context.add_stream_chunk_and_type(error_msg, ChunkEnum.ERROR)

    async def _process_responses(self, responses, step_name):
        """Process streaming responses and send as think chunks"""
        current_phase = None
        phase_content = ""
        research_goal = ""
        web_sites = []
        keepalive_shown = False

        async for response in responses:
            # Check response status
            if hasattr(response, "status_code") and response.status_code != 200:
                error_msg = f"HTTP错误码：{response.status_code}"
                if hasattr(response, "code"):
                    error_msg += f", 错误码：{response.code}"
                if hasattr(response, "message"):
                    error_msg += f", 错误信息：{response.message}"
                await self.context.add_stream_chunk_and_type(error_msg + "\n", ChunkEnum.THINK)
                continue

            if hasattr(response, "output") and response.output:
                message = response.output.get("message", {})
                phase = message.get("phase")
                content = message.get("content", "")
                status = message.get("status")
                extra = message.get("extra", {})

                # Phase change detection
                if phase != current_phase:
                    if current_phase and phase_content:
                        phase_end_msg = f"\n{current_phase} 阶段完成"
                        if step_name == "第一步：模型反问确认" and current_phase == "answer":
                            phase_end_msg = "\n模型反问阶段完成"
                        await self.context.add_stream_chunk_and_type(phase_end_msg + "\n", ChunkEnum.THINK)

                    current_phase = phase
                    phase_content = ""
                    keepalive_shown = False

                    # Phase start message
                    phase_start_msg = f"\n进入 {phase} 阶段"
                    if step_name == "第一步：模型反问确认" and phase == "answer":
                        phase_start_msg = "\n进入模型反问阶段"
                    await self.context.add_stream_chunk_and_type(phase_start_msg + "\n", ChunkEnum.THINK)

                # Handle WebResearch phase special information
                if phase == "WebResearch":
                    if extra.get("deep_research", {}).get("research"):
                        research_info = extra["deep_research"]["research"]

                        # Handle streamingQueries status
                        if status == "streamingQueries":
                            if "researchGoal" in research_info:
                                goal = research_info["researchGoal"]
                                if goal:
                                    research_goal += goal
                                    await self.context.add_stream_chunk_and_type(
                                        f"\n   研究目标: {goal}",
                                        ChunkEnum.THINK,
                                    )

                        # Handle streamingWebResult status
                        elif status == "streamingWebResult":
                            if "webSites" in research_info:
                                sites = research_info["webSites"]
                                if sites and sites != web_sites:
                                    web_sites = sites
                                    sites_info = f"\n   找到 {len(sites)} 个相关网站:\n"
                                    for i, site in enumerate(sites, 1):
                                        sites_info += f"     {i}. {site.get('title', '无标题')}\n"
                                        sites_info += f"        描述: {site.get('description', '无描述')[:100]}...\n"
                                        sites_info += f"        URL: {site.get('url', '无链接')}\n"
                                        if site.get("favicon"):
                                            sites_info += f"        图标: {site['favicon']}\n"
                                        sites_info += "\n"
                                    await self.context.add_stream_chunk_and_type(sites_info + "\n", ChunkEnum.THINK)

                        # Handle WebResultFinished status
                        elif status == "WebResultFinished":
                            finish_msg = f"\n   网络搜索完成，共找到 {len(web_sites)} 个参考信息源"
                            if research_goal:
                                finish_msg += f"\n   研究目标: {research_goal}"
                            await self.context.add_stream_chunk_and_type(finish_msg + "\n", ChunkEnum.THINK)

                # Send content as think chunks
                if content:
                    phase_content += content
                    if "第一步" in step_name:
                        await self.context.add_stream_chunk_and_type(content, ChunkEnum.THINK)
                    else:
                        await self.context.add_stream_chunk_and_type(content, ChunkEnum.ANSWER)

                # Handle status changes
                if status and status != "typing":
                    status_msg = f"\n   状态: {status}"

                    # Add status descriptions
                    if status == "streamingQueries":
                        status_msg += "\n   → 正在生成研究目标和搜索查询（WebResearch阶段）"
                    elif status == "streamingWebResult":
                        status_msg += "\n   → 正在执行搜索、网页阅读和代码执行（WebResearch阶段）"
                    elif status == "WebResultFinished":
                        status_msg += "\n   → 网络搜索阶段完成（WebResearch阶段）"

                    await self.context.add_stream_chunk_and_type(status_msg + "\n", ChunkEnum.THINK)

                # Handle finished status with token usage
                if status == "finished":
                    if hasattr(response, "usage") and response.usage:
                        usage = response.usage
                        usage_msg = f"\n    Token消耗统计:\n"
                        usage_msg += f"      输入tokens: {usage.get('input_tokens', 0)}\n"
                        usage_msg += f"      输出tokens: {usage.get('output_tokens', 0)}\n"
                        usage_msg += f"      请求ID: {response.get('request_id', '未知')}"
                        await self.context.add_stream_chunk_and_type(usage_msg + "\n", ChunkEnum.THINK)

                if phase == "KeepAlive":
                    if not keepalive_shown:
                        await self.context.add_stream_chunk_and_type(
                            "当前步骤已经完成，准备开始下一步骤工作\n",
                            ChunkEnum.THINK,
                        )
                        keepalive_shown = True
                    continue

        # Final phase completion message
        if current_phase and phase_content:
            phase_end_msg = f"\n{current_phase} 阶段完成"
            if step_name == "第一步：模型反问确认" and current_phase == "answer":
                phase_end_msg = "\n模型反问阶段完成"
            await self.context.add_stream_chunk_and_type(phase_end_msg + "\n", ChunkEnum.THINK)

        return phase_content


async def main():
    from flowllm.app import FlowLLMApp

    async with FlowLLMApp(load_default_config=True):

        context = FlowContext(query="茅台公司未来业绩", stream_queue=asyncio.Queue())
        op = DashscopeDeepResearchOp()
        task = asyncio.create_task(op.async_call(context=context))

        while True:
            stream_chunk = await context.stream_queue.get()
            if stream_chunk.done:
                print("\nend")
                break

            else:
                print(stream_chunk.chunk, end="")

        await task


if __name__ == "__main__":
    asyncio.run(main())
