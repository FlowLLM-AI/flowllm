import os

import dashscope
from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_llm_op import BaseLLMOp
from flowllm.storage.cache.data_cache import DataCache


@C.register_op()
class DashscopeDeepResearchOp(BaseLLMOp):
    file_path: str = __file__

    """
    Dashscope deep research operation using Alibaba's Qwen-deep-research model.
    
    This operation performs deep research using Dashscope's Generation API with the 
    qwen-deep-research model. It handles the multi-phase research process including
    model questioning, web research, and result generation.
    """

    def __init__(self,
                 model: str = "qwen-deep-research",
                 enable_print: bool = True,
                 enable_cache: bool = True,
                 cache_path: str = "./dashscope_deep_research_cache",
                 cache_expire_hours: float = 24,
                 max_retries: int = 3,
                 return_only_content: bool = True,
                 **kwargs):
        super().__init__(**kwargs)

        self.model = model
        self.enable_print = enable_print
        self.enable_cache = enable_cache
        self.cache_expire_hours = cache_expire_hours
        self.max_retries = max_retries
        self.return_only_content = return_only_content

        # Ensure API key is available
        self.api_key = os.getenv("FLOW_DASHSCOPE_API_KEY")
        self.cache_path: str = cache_path
        self._cache: DataCache | None = None

    @property
    def cache(self):
        if self.enable_cache and self._cache is None:
            self._cache = DataCache(self.cache_path)
        return self._cache

    def process_responses(self, responses, step_name):
        """Process streaming responses from the deep research model"""
        current_phase = None
        phase_content = ""
        research_goal = ""
        web_sites = []
        keepalive_shown = False  # 标记是否已经显示过KeepAlive提示

        for response in responses:
            # 检查响应状态码
            if hasattr(response, 'status_code') and response.status_code != 200:
                logger.warning(f"HTTP返回码：{response.status_code}")
                if hasattr(response, 'code'):
                    logger.warning(f"错误码：{response.code}")
                if hasattr(response, 'message'):
                    logger.warning(f"错误信息：{response.message}")
                continue

            if hasattr(response, 'output') and response.output:
                message = response.output.get('message', {})
                phase = message.get('phase')
                content = message.get('content', '')
                status = message.get('status')
                extra = message.get('extra', {})

                # 阶段变化检测
                if phase != current_phase:
                    if current_phase and phase_content:
                        # 根据阶段名称和步骤名称来显示不同的完成描述
                        if step_name == "第一步：模型反问确认" and current_phase == "answer":
                            logger.info("模型反问阶段完成")
                        else:
                            logger.info(f"{current_phase} 阶段完成")
                    current_phase = phase
                    phase_content = ""
                    keepalive_shown = False  # 重置KeepAlive提示标记

                    # 根据阶段名称和步骤名称来显示不同的描述
                    if step_name == "第一步：模型反问确认" and phase == "answer":
                        logger.info("进入模型反问阶段")
                    else:
                        logger.info(f"进入 {phase} 阶段")

                # 处理WebResearch阶段的特殊信息
                if phase == "WebResearch":
                    if extra.get('deep_research', {}).get('research'):
                        research_info = extra['deep_research']['research']

                        # 处理streamingQueries状态
                        if status == "streamingQueries":
                            if 'researchGoal' in research_info:
                                goal = research_info['researchGoal']
                                if goal:
                                    research_goal += goal
                                    if self.enable_print:
                                        print(f"   研究目标: {goal}", end='', flush=True)

                        # 处理streamingWebResult状态
                        elif status == "streamingWebResult":
                            if 'webSites' in research_info:
                                sites = research_info['webSites']
                                if sites and sites != web_sites:  # 避免重复显示
                                    web_sites = sites
                                    if self.enable_print:
                                        print(f"   找到 {len(sites)} 个相关网站:")
                                        for i, site in enumerate(sites, 1):
                                            print(f"     {i}. {site.get('title', '无标题')}")
                                            print(f"        描述: {site.get('description', '无描述')[:100]}...")
                                            print(f"        URL: {site.get('url', '无链接')}")
                                            if site.get('favicon'):
                                                print(f"        图标: {site['favicon']}")
                                            print()

                        # 处理WebResultFinished状态
                        elif status == "WebResultFinished":
                            if self.enable_print:
                                print(f"   网络搜索完成，共找到 {len(web_sites)} 个参考信息源")
                                if research_goal:
                                    print(f"   研究目标: {research_goal}")

                # 累积内容并显示
                if content:
                    phase_content += content
                    # 实时显示内容
                    if self.enable_print:
                        print(content, end='', flush=True)

                # 显示阶段状态变化
                if status and status != "typing":
                    if self.enable_print:
                        print(f"   状态: {status}")

                    # 显示状态说明
                    if status == "streamingQueries":
                        if self.enable_print:
                            print("   → 正在生成研究目标和搜索查询（WebResearch阶段）")
                    elif status == "streamingWebResult":
                        if self.enable_print:
                            print("   → 正在执行搜索、网页阅读和代码执行（WebResearch阶段）")
                    elif status == "WebResultFinished":
                        if self.enable_print:
                            print("   → 网络搜索阶段完成（WebResearch阶段）")

                # 当状态为finished时，显示token消耗情况
                if status == "finished":
                    if hasattr(response, 'usage') and response.usage:
                        usage = response.usage
                        if self.enable_print:
                            print(f"    Token消耗统计:")
                            print(f"      输入tokens: {usage.get('input_tokens', 0)}")
                            print(f"      输出tokens: {usage.get('output_tokens', 0)}")
                            print(f"      请求ID: {response.get('request_id', '未知')}")

                if phase == "KeepAlive":
                    # 只在第一次进入KeepAlive阶段时显示提示
                    if not keepalive_shown:
                        if self.enable_print:
                            print("当前步骤已经完成，准备开始下一步骤工作")
                        keepalive_shown = True
                    continue

        if current_phase and phase_content:
            if step_name == "第一步：模型反问确认" and current_phase == "answer":
                logger.info("模型反问阶段完成")
            else:
                logger.info(f"{current_phase} 阶段完成")

        return phase_content

    def call_deep_research_model(self, messages, step_name):
        """Call the deep research model with the given messages"""
        if self.enable_print:
            print(f"\n=== {step_name} ===")

        try:
            responses = dashscope.Generation.call(
                api_key=self.api_key,
                model=self.model,
                messages=messages,
                # qwen-deep-research模型目前仅支持流式输出
                stream=True
                # incremental_output=True 使用增量输出请添加此参数
            )

            return self.process_responses(responses, step_name)

        except Exception as e:
            logger.error(f"调用API时发生错误: {e}")
            return ""

    def execute(self):
        """Execute the Dashscope deep research operation"""
        # Get query from context
        query = self.context.query

        # Check cache first
        if self.enable_cache and self.cache:
            cached_result = self.cache.load(query)
            if cached_result:
                if self.return_only_content:
                    self.context.dashscope_deep_research_result = cached_result.get("content", "")
                else:
                    self.context.dashscope_deep_research_result = cached_result
                return

        # 第一步：模型反问确认
        # 模型会分析用户问题，提出细化问题来明确研究方向
        messages = [{'role': 'user', 'content': query}]
        step1_content = self.call_deep_research_model(messages, "第一步：模型反问确认")

        # 第二步：深入研究
        # 基于第一步的反问内容，模型会执行完整的研究流程
        messages = [
            {'role': 'user', 'content': query},
            {'role': 'assistant', 'content': step1_content},  # 包含模型的反问内容
            {'role': 'user', 'content': '帮我生成完整且逻辑性的报告'}
        ]

        result_content = self.call_deep_research_model(messages, "第二步：深入研究")

        if self.enable_print:
            print(result_content)
            print("\n 研究完成！")

        # Prepare final result
        final_result = {
            "query": query,
            "step1_content": step1_content,
            "final_result": result_content,
            "model": self.model
        }

        # Cache the result if enabled
        if self.enable_cache and self.cache:
            self.cache.save(query, final_result, expire_hours=self.cache_expire_hours)

        # Set context
        if self.return_only_content:
            self.context.dashscope_deep_research_result = result_content
        else:
            self.context.dashscope_deep_research_result = final_result


def main():
    C.set_default_service_config().init_by_service_config()

    op = DashscopeDeepResearchOp(enable_print=True, enable_cache=True)

    context = FlowContext(query="中国电解铝行业值得投资吗，有哪些值得投资的标的，各个标的之间需要对比优劣势")
    op(context=context)
    print(context.dashscope_deep_research_result)


if __name__ == "__main__":
    main()
