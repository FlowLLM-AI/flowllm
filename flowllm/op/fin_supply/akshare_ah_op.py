from functools import partial

import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.context.service_context import C
from flowllm.op import BaseOp, BaseRayOp
from flowllm.utils.eastmoney_utils import get_ah_mapping, get_a_stock_df, get_hk_stock_df, get_forex_df


@C.register_op(register_app="FlowLLM")
class AkshareAhOp(BaseRayOp):

    def __init__(self,
                 enable_cache: bool = True,
                 cache_expire_hours: float = 24,
                 **kwargs):
        super().__init__(enable_cache=enable_cache, cache_expire_hours=cache_expire_hours, **kwargs)

    def prepare_raw_data(self):
        ah_df: pd.DataFrame = self.save_load_cache("ah_mapping", fn=get_ah_mapping,
                                                   dtype={"a_code": str, "hk_code": str})
        self.context.ah_df = ah_df

        hk_forex_df: pd.DataFrame = self.save_load_cache("hk_forex", fn=partial(get_forex_df, "HKDCNYC"))
        self.context.hk_forex_df = hk_forex_df

        self.context.stock_dict = {}
        a_dt_size_dict = {}
        for line in tqdm(ah_df.to_dict(orient="records"), desc="collect code df"):
            a_code = line["a_code"]
            hk_code = line["hk_code"]
            name = line["name"]

            a_stock_df = self.save_load_cache(f"{a_code}", fn=partial(get_a_stock_df, a_code))
            hk_stock_df = self.save_load_cache(f"{hk_code}", fn=partial(get_hk_stock_df, hk_code))

            self.context.stock_dict[name] = {
                "a_code": a_code,
                "hk_code": hk_code,
                "a_stock_df": a_stock_df,
                "hk_stock_df": hk_stock_df,
            }

            a_dt_list = sorted(a_stock_df.loc[:, "date"].unique())
            hk_dt_list = sorted(hk_stock_df.loc[:, "date"].unique())
            min_hk_dt = min(hk_dt_list)
            for dt in a_dt_list:
                if dt < min_hk_dt:
                    continue

                if dt not in a_dt_size_dict:
                    a_dt_size_dict[dt] = 0
                a_dt_size_dict[dt] += 1

        for dt, cnt in sorted(a_dt_size_dict.items(), key=lambda x: x[0]):
            logger.info(f"{dt}: {cnt}")
            assert cnt > 1

        self.context.a_dt_list = sorted(a_dt_size_dict.keys())

    def prepare_feature_data(self):
        f_op = self.ops[0]
        result = self.submit_and_join_parallel_op(op=f_op,
                                                  a_dt=self.context.a_dt_list,
                                                  ah_df=self.context.ah_df,
                                                  hk_forex_df=self.context.hk_forex_df,
                                                  stock_dict=self.context.stock_dict)

        df = pd.DataFrame(result)
        self.cache.save("feature_df", df)

    def execute(self):
        self.prepare_raw_data()

        self.prepare_feature_data()


class AkshareAhFeatureOp(BaseOp):
    def execute(self):
        # actor_index = self.context.actor_index
        a_dt = self.context.a_dt
        result = []
        for name, stock_info in self.context.stock_dict.items():
            t_result = {
                "dt": a_dt,
                "name": name,
                "code": stock_info["a_code"] + "+" + stock_info["hk_code"],
            }
            result.append(t_result)

        return result


def main():
    from flowllm.app import FlowLLMApp
    with FlowLLMApp(load_default_config=True) as app:
        app.service_config.ray_max_workers = 8

        op = AkshareAhOp()
        op = op << AkshareAhFeatureOp()
        print(op.call())


if __name__ == "__main__":
    main()
