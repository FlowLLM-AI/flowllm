import asyncio

from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode, AsyncWebCrawler
from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.enumeration.role import Role
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall
from flowllm.utils.common_utils import get_datetime
from flowllm.utils.web_utils import get_random_user_agent


class ThsBaseOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(self,
                 url_key: str = "",
                 tool_description: str = "",
                 max_content_len: int = 30000,
                 llm: str = "qwen3_80b_instruct",
                 language: str = "zh",
                 enable_cache: bool = True,
                 cache_expire_hours: float = 1,
                 **kwargs):

        super().__init__(llm=llm,
                         language=language,
                         enable_cache=enable_cache,
                         cache_expire_hours=cache_expire_hours,
                         **kwargs)

        self.browser_config = BrowserConfig(
            headless=True,
            java_script_enabled=True,
            user_agent=get_random_user_agent(),
            viewport={"width": 1280, "height": 800},
            verbose=True)

        self.crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.DISABLED,
            page_timeout=9000,
            verbose=True)

        self.url: str = f"https://basic.10jqka.com.cn/{{code}}/{url_key}.html#stockpage"
        self.tool_description: str = tool_description
        self.max_content_len: int = max_content_len

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "description": self.tool_description,
            "input_schema": {
                "code": {
                    "type": "string",
                    "description": "stock code",
                    "required": True
                },
            }
        })

    async def async_execute(self):
        code: str = self.input_dict["code"]

        if self.enable_cache:
            cached_result = self.cache.load(code)
            if cached_result:
                self.set_result(cached_result["response_content"])
                return

        url = self.url.format(code=code)

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(
                url=url,
                config=self.crawler_config,
                # js_code="window.scrollTo(0, document.body.scrollHeight);",
                # wait_for="document.querySelector('.loaded')"
            )
            content = result.markdown[:self.max_content_len]
            extract_content_prompt = self.prompt_format(prompt_name="extract_content_prompt",
                                                        date=get_datetime(),
                                                        code=code,
                                                        content=content)
            assistant_message = await self.llm.achat(messages=[Message(role=Role.USER, content=extract_content_prompt)])
            self.set_result(assistant_message.content)

            final_result = {
                "code": code,
                "raw": result.markdown,
                "response_content": assistant_message.content,
                "model": self.llm.model_name,
            }

            if self.enable_cache:
                self.cache.save(code, final_result, expire_hours=self.cache_expire_hours)


@C.register_op(register_app="FlowLLM")
class ThsCompanyOp(ThsBaseOp):

    def __init__(self, **kwargs):
        url_key: str = "company"
        tool_description: str = "通过股票代码获取公司资料信息，例如：详细情况，高管介绍，发行相关，参控股公司。"
        super().__init__(url_key=url_key, tool_description=tool_description, **kwargs)


@C.register_op(register_app="FlowLLM")
class ThsHolderOp(ThsBaseOp):

    def __init__(self, **kwargs):
        url_key: str = "holder"
        tool_description: str = "通过股票代码获取股东研究信息，例如：股东人数、十大流通股东、十大股东、十大债券持有人、控股层级关系。"
        super().__init__(url_key=url_key, tool_description=tool_description, **kwargs)


@C.register_op(register_app="FlowLLM")
class ThsOperateOp(ThsBaseOp):

    def __init__(self, **kwargs):
        url_key: str = "operate"
        tool_description: str = "通过股票代码获取经营分析信息，例如：主营介绍、运营业务数据、主营构成分析、主要客户及供应商、董事会经营评述、产品价格。"
        super().__init__(url_key=url_key, tool_description=tool_description, **kwargs)


@C.register_op(register_app="FlowLLM")
class ThsEquityOp(ThsBaseOp):

    def __init__(self, **kwargs):
        url_key: str = "equity"
        tool_description: str = "通过股票代码获取股本结构信息，例如：解禁时间表、总股本构成、A股结构图、历次股本变动"
        super().__init__(url_key=url_key, tool_description=tool_description, **kwargs)


@C.register_op(register_app="FlowLLM")
class ThsCapitalOp(ThsBaseOp):

    def __init__(self, **kwargs):
        url_key: str = "capital"
        tool_description: str = "通过股票代码获取资本运作信息，例如：募集资金来源、项目投资、收购兼并、股权投资、参股IPO、股权转让、关联交易、质押解冻。"
        super().__init__(url_key=url_key, tool_description=tool_description, **kwargs)


@C.register_op(register_app="FlowLLM")
class ThsWorthOp(ThsBaseOp):

    def __init__(self, **kwargs):
        url_key: str = "worth"
        tool_description: str = "通过股票代码获取盈利预测信息，例如：业绩预测、业绩预测详表、研报评级"
        super().__init__(url_key=url_key, tool_description=tool_description, **kwargs)


@C.register_op(register_app="FlowLLM")
class ThsNewsOp(ThsBaseOp):

    def __init__(self, **kwargs):
        url_key: str = "news"
        tool_description: str = "通过股票代码获取新闻公告信息，例如：新闻与股价联动、公告列表、热点新闻列表、研报列表"
        super().__init__(url_key=url_key, tool_description=tool_description, **kwargs)


@C.register_op(register_app="FlowLLM")
class ThsConceptOp(ThsBaseOp):

    def __init__(self, **kwargs):
        url_key: str = "concept"
        tool_description: str = "通过股票代码获取概念题材信息，例如：常规概念、其他概念、题材要点、概念对比"
        super().__init__(url_key=url_key, tool_description=tool_description, **kwargs)


@C.register_op(register_app="FlowLLM")
class ThsPositionOp(ThsBaseOp):

    def __init__(self, **kwargs):
        url_key: str = "position"
        tool_description: str = "通过股票代码获取主力持仓信息，例如：机构持股汇总、机构持股明细、被举牌情况、IPO获配机构"
        super().__init__(url_key=url_key, tool_description=tool_description, **kwargs)


@C.register_op(register_app="FlowLLM")
class ThsFinanceOp(ThsBaseOp):

    def __init__(self, **kwargs):
        url_key: str = "finance"
        tool_description: str = "通过股票代码获取财务分析信息，例如：财务诊断、财务指标、指标变动说明、资产负债构成、财务报告、杜邦分析"
        super().__init__(url_key=url_key, tool_description=tool_description, **kwargs)


@C.register_op(register_app="FlowLLM")
class ThsBonusOp(ThsBaseOp):

    def __init__(self, **kwargs):
        url_key: str = "bonus"
        tool_description: str = "通过股票代码获取分红融资信息，例如：分红诊断、分红情况、增发机构获配明细、增发概况、配股概况"
        super().__init__(url_key=url_key, tool_description=tool_description, **kwargs)


@C.register_op(register_app="FlowLLM")
class ThsEventOp(ThsBaseOp):

    def __init__(self, **kwargs):
        url_key: str = "event"
        tool_description: str = "通过股票代码获取公司大事信息，例如：高管持股变动、股东持股变动、担保明细、违规处理、机构调研、投资者互动"
        super().__init__(url_key=url_key, tool_description=tool_description, **kwargs)


@C.register_op(register_app="FlowLLM")
class ThsFieldOp(ThsBaseOp):

    def __init__(self, **kwargs):
        url_key: str = "field"
        tool_description: str = "通过股票代码获取行业对比信息，例如：行业地位、行业新闻"
        super().__init__(url_key=url_key, tool_description=tool_description, **kwargs)

async def main():
    from flowllm.app import FlowLLMApp
    async with FlowLLMApp(load_default_config=True):
        code = "601899"
        context = FlowContext(code=code)

        ops = [
            ThsCompanyOp(),
            ThsHolderOp(),
            ThsOperateOp(),
            ThsEquityOp(),
            ThsCapitalOp(),
            ThsWorthOp(),
            ThsNewsOp(),
            ThsConceptOp(),
            ThsPositionOp(),
            ThsFinanceOp(),
            ThsBonusOp(),
            ThsEventOp(),
            ThsFieldOp()
        ]
        for op in ops:
            await op.async_call(context=context)
            logger.info(op.output)


if __name__ == "__main__":
    asyncio.run(main())
