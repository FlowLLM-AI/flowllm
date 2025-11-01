import asyncio
import json
import sys
from io import StringIO
from typing import Optional, TYPE_CHECKING

import pandas as pd
from loguru import logger

if TYPE_CHECKING:
    import akshare as ak

from flowllm.context import FlowContext
from flowllm.context.service_context import C
from flowllm.enumeration.role import Role
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall
from flowllm.utils.common_utils import get_datetime, extract_content


@C.register_op(register_app="FlowLLM")
class AkshareMarketOp(BaseAsyncToolOp):

    def __init__(
        self,
        enable_cache: bool = True,
        cache_expire_hours: float = 0.1,
        **kwargs,
    ):
        super().__init__(enable_cache=enable_cache, cache_expire_hours=cache_expire_hours, **kwargs)

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": "Query real-time quotes for A-share stocks",
                "input_schema": {
                    "code": {
                        "type": "string",
                        "description": "A-share stocks code",
                        "required": True,
                    },
                },
            },
        )

    @staticmethod
    def download_a_stock_df():
        import akshare as ak

        stock_sh_a_spot_em_df = ak.stock_sh_a_spot_em()
        stock_sz_a_spot_em_df = ak.stock_sz_a_spot_em()
        stock_bj_a_spot_em_df = ak.stock_bj_a_spot_em()

        df: pd.DataFrame = pd.concat([stock_sh_a_spot_em_df, stock_sz_a_spot_em_df, stock_bj_a_spot_em_df], axis=0)
        df = df.drop(columns=["序号"])
        df = df.reset_index(drop=True)
        df = df.sort_values(by="代码")
        return df

    async def async_execute(self):
        code: str = self.input_dict["code"]

        df: Optional[pd.DataFrame] = None
        if self.enable_cache:
            df = self.cache.load(code, dtype={"代码": str})

        if df is None:
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(C.thread_pool, self.download_a_stock_df)  ## noqa

        if self.enable_cache:
            self.cache.save(code, df, expire_hours=self.cache_expire_hours)

        result = df.loc[df["代码"] == code, :].to_dict(orient="records")[-1]
        response: str = f"{code}的实时行情: {json.dumps(result, ensure_ascii=False)}"
        self.set_result(response)


@C.register_op(register_app="FlowLLM")
class AkshareCalculateOp(BaseAsyncToolOp):
    file_path = __file__

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": self.get_prompt("tool_description"),
                "input_schema": {
                    "code": {
                        "type": "string",
                        "description": "A-share stock code",
                        "required": True,
                    },
                    "query": {
                        "type": "string",
                        "description": "user query",
                        "required": True,
                    },
                },
            },
        )

    async def async_execute(self):
        code: str = self.input_dict["code"]
        query: str = self.input_dict["query"]

        akshare_code_prompt: str = self.prompt_format(
            prompt_name="akshare_code_prompt",
            code=code,
            query=query,
            current_date=get_datetime(),
            example=self.get_prompt("akshare_code_example"),
        )

        messages = [Message(role=Role.USER, content=akshare_code_prompt)]
        old_stdout = sys.stdout
        redirected_output = sys.stdout = StringIO()

        for i in range(3):

            def get_code(message: Message):
                return extract_content(message.content, language_tag="python")

            result_code = await self.llm.achat(messages=messages, callback_fn=get_code)
            logger.info(f"i={i} result_code=\n{result_code}")
            messages.append(Message(role=Role.ASSISTANT, content=result_code))

            try:
                exec(result_code)
                code_result = redirected_output.getvalue()
                messages.append(Message(role=Role.USER, content=code_result))
                break

            except Exception as e:
                logger.info(f"{self.name} encounter exception! error={e.args}")
                messages.append(Message(role=Role.USER, content=str(e)))

        sys.stdout = old_stdout
        self.set_result(messages[-1].content)


async def async_main():
    # op = AkshareTradeOp()
    # context = FlowContext(code="601899")
    # await op.async_call(context=context)
    # print(op.output)
    from flowllm.app import FlowLLMApp

    async with FlowLLMApp(load_default_config=True):
        op = AkshareCalculateOp()
        context = FlowContext(code="601899", query="最近五日成交量有放量吗？最近五日macd有金叉吗？")
        await op.async_call(context=context)
        print(op.output)


if __name__ == "__main__":
    asyncio.run(async_main())
