import json
from typing import List

import akshare as ak
import pandas as pd
from flowllm.op.base_llm_op import BaseLLMOp
from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.enumeration.role import Role
from flowllm.schema.message import Message
from flowllm.storage.cache.data_cache import DataCache
from flowllm.utils.timer import timer


@C.register_op()
class GetAkACodeOp(BaseLLMOp):
    file_path: str = __file__

    def __init__(self, language: str = "zh", llm="qwen3_30b_instruct", **kwargs):
        super().__init__(language=language, llm=llm, **kwargs)

    @staticmethod
    def download_a_stock_df():
        cache = DataCache()
        save_df_key: str = "all_a_stock_name_code"
        if not cache.exists(save_df_key):
            stock_sh_a_spot_em_df = ak.stock_sh_a_spot_em()
            stock_sz_a_spot_em_df = ak.stock_sz_a_spot_em()
            stock_bj_a_spot_em_df = ak.stock_bj_a_spot_em()

            df: pd.DataFrame = pd.concat([stock_sh_a_spot_em_df, stock_sz_a_spot_em_df, stock_bj_a_spot_em_df], axis=0)
            df = df.drop(columns=["序号"])
            df = df.reset_index(drop=True)
            df = df.sort_values(by="代码")
            cache.save(save_df_key, df, expire_hours=0.25)

        df = cache.load(save_df_key, dtype={"代码": str})
        return df

    def get_name_code_dict(self) -> dict:
        df = self.download_a_stock_df()

        name_code_dict = {}
        for line in df.to_dict(orient="records"):
            name = line["名称"].replace(" ", "")
            code = line["代码"]
            name_code_dict[name] = code
        logger.info(f"name_code_dict.size={len(name_code_dict)} content={str(name_code_dict)[:50]}...")
        return name_code_dict

    @staticmethod
    def split_list(array_list: list, n: int):
        if n <= 0:
            raise ValueError

        length = len(array_list)
        base_size = length // n
        remainder = length % n

        start = 0
        for i in range(n):
            size = base_size + (1 if i < remainder else 0)
            end = start + size
            yield array_list[start:end]
            start = end

    @timer()
    def find_stock_codes(self, stock_names: List[str]):
        stock_names = "\n".join([x.strip() for x in stock_names if x])
        prompt = self.prompt_format(prompt_name="find_stock_name",
                                    stock_names=stock_names,
                                    query=self.context.query)
        logger.info(f"prompt={prompt}")

        def callback_fn(msg: Message):
            content = msg.content
            if "```" in content:
                content = content.split("```")[1]
                content = content.strip("json")
            content = json.loads(content.strip())
            return content

        codes: List[str] = self.llm.chat(messages=[Message(role=Role.USER, content=prompt)],
                                         enable_stream_print=False,
                                         callback_fn=callback_fn)
        return codes

    def execute(self):
        name_code_dict = self.get_name_code_dict()
        stock_names = list(name_code_dict.keys())
        for p_stock_names in self.split_list(stock_names, n=1):
            self.submit_task(self.find_stock_codes, stock_names=p_stock_names)
            # time.sleep(1)

        stock_names = sorted(set(self.join_task()))
        self.context.code_infos = {name_code_dict[n]: {"股票名称": n} for n in stock_names if n in name_code_dict}
        logger.info(f"code_infos={self.context.code_infos}")


if __name__ == "__main__":
    C.set_service_config().init_by_service_config()
    context = FlowContext(query="茅台和五粮现在价格多少？")

    op = GetAkACodeOp()
    op(context=context)
