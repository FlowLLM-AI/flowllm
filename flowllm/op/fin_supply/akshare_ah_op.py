from functools import partial
from typing import List

import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.context.service_context import C
from flowllm.op import BaseOp, BaseRayOp
from flowllm.utils.eastmoney_utils import get_ah_mapping, get_a_stock_df, get_hk_stock_df, get_forex_df
from flowllm.utils.plot_utils import plot_figure


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
        dt_size_dict = {}
        for line in tqdm(ah_df.to_dict(orient="records"), desc="collect code df"):
            a_code = line["a_code"]
            hk_code = line["hk_code"]
            name = line["name"]

            a_hfq_stock_df = self.save_load_cache(f"{a_code}_hfq",
                                                  fn=partial(get_a_stock_df, code=a_code, adjust="hfq"))
            hk_hfq_stock_df = self.save_load_cache(f"{hk_code}_hfq",
                                                   fn=partial(get_hk_stock_df, code=hk_code, adjust="hfq"))

            a_org_stock_df = self.save_load_cache(f"{a_code}_org",
                                                  fn=partial(get_a_stock_df, code=a_code, adjust=""))
            hk_org_stock_df = self.save_load_cache(f"{hk_code}_org",
                                                   fn=partial(get_hk_stock_df, code=hk_code, adjust=""))

            hk_dt_list = sorted(hk_org_stock_df.loc[:, "date"].unique())
            min_hk_dt = min(hk_dt_list)
            a_dt_list = sorted(a_org_stock_df.loc[:, "date"].unique())
            a_dt_list = [x for x in a_dt_list if x >= min_hk_dt]

            self.context.stock_dict[name] = {
                "a_code": a_code,
                "hk_code": hk_code,
                "a_hfq_stock_df": a_hfq_stock_df,
                "hk_hfq_stock_df": hk_hfq_stock_df,
                "a_org_stock_df": a_org_stock_df,
                "hk_org_stock_df": hk_org_stock_df,
                "hk_dt_list": hk_dt_list,
                "a_dt_list": a_dt_list,
            }

            for dt in a_dt_list:
                if dt not in dt_size_dict:
                    dt_size_dict[dt] = 0
                dt_size_dict[dt] += 1

            for dt in hk_dt_list:
                if dt not in dt_size_dict:
                    dt_size_dict[dt] = 0
                dt_size_dict[dt] += 1

        for dt, cnt in sorted(dt_size_dict.items(), key=lambda x: x[0]):
            logger.info(f"{dt}: {cnt}")
            assert cnt > 1

        self.context.dt_list = sorted(dt_size_dict.keys())

    def prepare_feature_data(self):
        f_op = self.ops[0]
        result = self.submit_and_join_parallel_op(op=f_op, dt=self.context.dt_list)

        df = pd.DataFrame(result).sort_values(["dt", "code"])
        self.cache.save("feature_df", df)

    def prepare_backtest(self):
        logger.info("start backtest")
        b_op = self.ops[1]

        feature_df = self.cache.load("feature_df")
        self.context.feature_df = feature_df
        logger.info(f"feature_df.shape={feature_df.shape}")
        dt_list = sorted(set(feature_df.loc[feature_df.a_flag == 1, "dt"]))
        logger.info(f"dt_list={dt_list[0]}...{dt_list[-1]} size={len(dt_list)}")

        result = self.submit_and_join_parallel_op(op=b_op, dt=dt_list[:-1])

        df = pd.DataFrame(result).sort_values(["dt"])
        self.cache.save("backtest_df", df)

        strategy_list = [x for x in df.columns.tolist() if "_uplift" in x]
        logger.info(f"find strategy_list={strategy_list}")

        plot_dict = {x: [x / 100 for x in df.loc[:, x].tolist()] for x in strategy_list}
        plot_figure(plot_dict, "ah_strategy.pdf")

    def execute(self):
        # self.prepare_raw_data()
        # self.prepare_feature_data()

        self.prepare_backtest()


class AkshareAhFeatureOp(BaseOp):

    @staticmethod
    def find_dt_nearest_index(dt: str, dt_list: List[str]):
        """
        Use binary search to find the index of the date that is closest to and not greater than dt.
        Time complexity: O(log n)
        """
        if not dt_list:
            return None

        left, right = 0, len(dt_list) - 1

        if dt < dt_list[left]:
            return None

        if dt >= dt_list[right]:
            return right

        while left < right:
            mid = (left + right + 1) // 2
            if dt_list[mid] <= dt:
                left = mid
            else:
                right = mid - 1

        return left


    def execute(self):
        # actor_index = self.context.actor_index
        result = []
        dt = self.context.dt
        hk_forex_df = self.context.hk_forex_df
        hk_forex_dt_list = sorted(hk_forex_df.loc[:, "date"].unique())
        hk_forex_dt = hk_forex_dt_list[self.find_dt_nearest_index(dt, hk_forex_dt_list)]
        hk_forex_ratio = hk_forex_df.loc[hk_forex_df.date == hk_forex_dt, "close"].values[0]

        for name, stock_info in self.context.stock_dict.items():
            t_result = {
                "dt": dt,
                "name": name,
                "code": stock_info["a_code"] + "+" + stock_info["hk_code"],
            }

            # a_hfq_stock_df = stock_info["a_hfq_stock_df"]
            # hk_hfq_stock_df = stock_info["hk_hfq_stock_df"]
            a_org_stock_df = stock_info["a_org_stock_df"]
            hk_org_stock_df = stock_info["hk_org_stock_df"]

            a_dt_list = stock_info["a_dt_list"]
            hk_dt_list = stock_info["hk_dt_list"]

            dt_a_index = self.find_dt_nearest_index(dt, a_dt_list)
            dt_hk_index = self.find_dt_nearest_index(dt, hk_dt_list)

            if dt_a_index is None or len(a_dt_list[:dt_a_index + 1]) < 2:
                continue

            if dt_hk_index is None or len(hk_dt_list[:dt_hk_index + 1]) < 2:
                continue

            next_a_index = dt_a_index + 1
            if len(a_dt_list) - 1 < next_a_index:
                next_a_index = dt_a_index

            next_hk_index = dt_hk_index + 1
            if len(hk_dt_list) - 1 < next_hk_index:
                next_hk_index = dt_hk_index

            current_a_close = a_org_stock_df.loc[a_org_stock_df.date == a_dt_list[dt_a_index], "close"].values[0]
            current_hk_close = hk_org_stock_df.loc[hk_org_stock_df.date == hk_dt_list[dt_hk_index], "close"].values[0]

            current_a_uplift = a_org_stock_df.loc[a_org_stock_df.date == a_dt_list[dt_a_index], "chg_pct"].values[0]
            current_hk_uplift = hk_org_stock_df.loc[hk_org_stock_df.date == hk_dt_list[dt_hk_index], "chg_pct"] \
                .values[0]

            next_a_uplift = a_org_stock_df.loc[a_org_stock_df.date == a_dt_list[next_a_index], "chg_pct"].values[0]
            next_hk_uplift = hk_org_stock_df.loc[hk_org_stock_df.date == hk_dt_list[next_hk_index], "chg_pct"].values[0]

            current_a_amount = a_org_stock_df.loc[a_org_stock_df.date == a_dt_list[dt_a_index], "amount"].values[0]
            current_hk_amount = hk_org_stock_df.loc[hk_org_stock_df.date == hk_dt_list[dt_hk_index], "amount"].values[0]

            t_result["current_hk_close"] = current_hk_close
            t_result["current_a_close"] = current_a_close
            t_result["hk_forex_ratio"] = hk_forex_ratio

            t_result["a_flag"] = 1 if dt in a_dt_list else 0
            t_result["hk_flag"] = 1 if dt in hk_dt_list else 0

            t_result["a_uplift"] = current_a_uplift
            t_result["hk_uplift"] = current_hk_uplift

            t_result["ah_amount"] = current_hk_amount / current_a_amount - 1

            t_result["ah_ratio"] = current_hk_close * hk_forex_ratio / current_a_close

            t_result["a_label"] = next_a_uplift
            t_result["hk_label"] = next_hk_uplift

            result.append(t_result)

        return result


class AkshareAhBacktestOp(BaseOp):

    def __init__(self, min_f_size: int = 5, **kwargs):
        super().__init__(**kwargs)
        self.min_f_size = min_f_size

    def execute(self):
        dt = self.context.dt
        feature_df: pd.DataFrame = self.context.feature_df
        dt_df: pd.DataFrame = feature_df.loc[feature_df.dt == dt]

        dt_df = dt_df.sort_values(by="ah_ratio", ascending=False)
        select_df = dt_df[:5]

        result = {
            "dt": dt,
            "size": len(dt_df),
            "select_names": ",".join(select_df.loc[:, "name"].tolist()),
            "select_uplift": select_df.loc[:, "a_label"].mean(),
            "all_uplift": dt_df.loc[:, "a_label"].mean(),
        }

        block_size = 10
        block_cnt = round(len(dt_df) / block_size)
        for i in range(block_size):
            result[f"p{i}_uplift"] = dt_df[i * block_cnt: i * block_cnt + block_cnt].loc[:, "a_label"].mean()
        return result

def main():
    from flowllm.app import FlowLLMApp
    with FlowLLMApp(load_default_config=True) as app:
        app.service_config.ray_max_workers = 8

        op = AkshareAhOp()
        op = op << AkshareAhFeatureOp() << AkshareAhBacktestOp()
        print(op.call())


if __name__ == "__main__":
    main()
