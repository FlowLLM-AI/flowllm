import asyncio
from functools import partial

import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.utils.eastmoney_utils import get_ah_mapping, get_a_stock_df, get_hk_stock_df, get_forex_df


@C.register_op(register_app="FlowLLM")
class AkshareAHOp(BaseAsyncToolOp):

    def __init__(self,
                 enable_cache: bool = True,
                 cache_expire_hours: float = 12,
                 **kwargs):
        super().__init__(enable_cache=enable_cache, cache_expire_hours=cache_expire_hours, **kwargs)

    async def async_execute(self):
        ah_df: pd.DataFrame = await self.async_save_load_cache("ah_mapping",
                                                               fn=get_ah_mapping,
                                                               dtype={"a_code": str, "hk_code": str})
        logger.info(f"ah_df=\n{ah_df}")

        hk_forex_df: pd.DataFrame = await self.async_save_load_cache("hk_forex",
                                                                     fn=partial(get_forex_df, "HKDCNYC"))
        logger.info(f"hk_forex_df=\n{hk_forex_df}")

        for line in tqdm(ah_df.to_dict(orient="records"), desc="collect code df"):
            a_code = line["a_code"]
            hk_code = line["hk_code"]
            await self.async_save_load_cache(f"{a_code}", fn=partial(get_a_stock_df, a_code))
            await self.async_save_load_cache(f"{hk_code}", fn=partial(get_hk_stock_df, hk_code))


async def main():
    from flowllm.app import FlowLLMApp
    async with FlowLLMApp(load_default_config=True):
        op = AkshareAHOp()
        context = FlowContext(code="601899")
        result = await op.async_call(context=context)
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
