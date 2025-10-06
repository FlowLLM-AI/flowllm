from functools import partial
from typing import List

import numpy as np
import pandas as pd
from loguru import logger
from scipy.stats import spearmanr, pearsonr
from sklearn.linear_model import Ridge
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
                 max_samples: int = 64,
                 **kwargs):
        super().__init__(enable_cache=enable_cache, cache_expire_hours=cache_expire_hours, **kwargs)
        self.max_samples: int = max_samples

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

            # a_qfq_stock_df = self.save_load_cache(f"{a_code}_qfq",
            #                                       fn=partial(get_a_stock_df, code=a_code, adjust="qfq"))
            # hk_qfq_stock_df = self.save_load_cache(f"{hk_code}_qfq",
            #                                        fn=partial(get_hk_stock_df, code=hk_code, adjust="qfq"))

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
                # "a_qfq_stock_df": a_qfq_stock_df,
                # "hk_qfq_stock_df": hk_qfq_stock_df,
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
        self.context.max_samples = self.max_samples

        feature_df = self.cache.load("feature_df")
        self.context.feature_df = feature_df
        logger.info(f"feature_df.shape={feature_df.shape}")
        dt_a_list = sorted(set(feature_df.loc[feature_df.a_flag == 1, "dt"]))
        self.context.dt_a_list = dt_a_list
        logger.info(f"dt_a_list={dt_a_list[0]}...{dt_a_list[-1]} size={len(dt_a_list)}")

        result = self.submit_and_join_parallel_op(op=b_op, dt=dt_a_list[self.max_samples + 1:-1])

        df = pd.DataFrame(result).sort_values(["dt"])
        self.cache.save("backtest_df", df)

        for key in ["model_ic", "model_ric", "rule_ic", "rule_ric"]:
            logger.info(f"{key} mean={df[key].mean()} std={df[key].std()}")

        strategy_list = [x for x in df.columns.tolist() if "_uplift" in x]
        logger.info(f"find strategy_list={strategy_list}")

        plot_dict = {x: [x / 100 for x in df.loc[:, x].tolist()] for x in strategy_list}
        plot_figure(plot_dict, "ah_strategy.pdf")

    def execute(self):
        self.prepare_raw_data()
        self.prepare_feature_data()

        # self.prepare_backtest()


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

            a_hfq_stock_df = stock_info["a_hfq_stock_df"]
            hk_hfq_stock_df = stock_info["hk_hfq_stock_df"]
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

            if dt_a_index < len(a_dt_list) - 1:
                next_a_index = dt_a_index + 1
            else:
                next_a_index = dt_a_index

            if dt_hk_index < len(hk_dt_list) - 1:
                next_hk_index = dt_hk_index + 1
            else:
                next_hk_index = dt_hk_index

            current_a_close = a_org_stock_df.loc[a_org_stock_df.date == a_dt_list[dt_a_index], "close"].values[0]
            current_hk_close = hk_org_stock_df.loc[hk_org_stock_df.date == hk_dt_list[dt_hk_index], "close"].values[0]

            current_a_uplift = a_org_stock_df.loc[a_org_stock_df.date == a_dt_list[dt_a_index], "chg_pct"].values[0]
            current_hk_uplift = hk_org_stock_df.loc[hk_org_stock_df.date == hk_dt_list[dt_hk_index], "chg_pct"] \
                .values[0]

            # 后复权计算label
            next_a_uplift = a_hfq_stock_df.loc[a_hfq_stock_df.date == a_dt_list[next_a_index], "chg_pct"].values[0]
            next_hk_uplift = hk_hfq_stock_df.loc[hk_hfq_stock_df.date == hk_dt_list[next_hk_index], "chg_pct"].values[0]

            current_a_amount = a_org_stock_df.loc[a_org_stock_df.date == a_dt_list[dt_a_index], "amount"].values[0]
            current_hk_amount = hk_org_stock_df.loc[hk_org_stock_df.date == hk_dt_list[dt_hk_index], "amount"].values[0]

            t_result["current_hk_close"] = current_hk_close
            t_result["current_a_close"] = current_a_close
            t_result["hk_forex_ratio"] = hk_forex_ratio

            t_result["a_flag"] = 1 if dt in a_dt_list else 0
            t_result["hk_flag"] = 1 if dt in hk_dt_list else 0

            t_result["a_uplift"] = current_a_uplift
            t_result["hk_uplift"] = current_hk_uplift

            for i in [1, 3, 5, 10, 20]:
                # 确保索引不为负数，使用max(0, ...)
                a_start_idx = max(0, dt_a_index - (i - 1))
                hk_start_idx = max(0, dt_hk_index - (i - 1))
                
                # 获取日期列表切片
                a_date_slice = a_dt_list[a_start_idx: dt_a_index + 1]
                hk_date_slice = hk_dt_list[hk_start_idx: dt_hk_index + 1]
                
                # 计算平均值，如果没有匹配的数据则为0
                a_matched = a_hfq_stock_df.loc[a_hfq_stock_df.date.isin(a_date_slice), "chg_pct"]
                hk_matched = hk_hfq_stock_df.loc[hk_hfq_stock_df.date.isin(hk_date_slice), "chg_pct"]
                
                t_result[f"avg_{i}d_a_pct"] = a_matched.mean() if len(a_matched) > 0 else 0
                t_result[f"avg_{i}d_hk_pct"] = hk_matched.mean() if len(hk_matched) > 0 else 0

            t_result["ah_amount"] = (current_hk_amount / current_a_amount - 1) if current_a_amount != 0 else 0

            t_result["ah_ratio"] = current_hk_close * hk_forex_ratio / current_a_close

            t_result["a_label"] = next_a_uplift
            t_result["hk_label"] = next_hk_uplift

            result.append(t_result)

        return result


class AkshareAhBacktestOp(BaseOp):

    def execute(self):
        dt = self.context.dt
        feature_df: pd.DataFrame = self.context.feature_df
        max_samples = self.context.max_samples
        train_dt_a_list: List[str] = [x for x in self.context.dt_a_list if x < dt][-max_samples:]

        train_df: pd.DataFrame = feature_df.loc[feature_df.dt.isin(train_dt_a_list)]
        test_df: pd.DataFrame = feature_df.loc[feature_df.dt == dt].copy()  # Fix: 使用.copy()避免SettingWithCopyWarning

        ah_ratio_key = "ah_ratio"
        label_key = "a_label"
        pred_key = "pred_y_nd"
        # dt,name,code,current_hk_close,current_a_close,hk_forex_ratio,a_flag,hk_flag,a_uplift,hk_uplift,ah_amount,ah_ratio,a_label,hk_label
        x_cols = [ah_ratio_key, "ah_amount"]  # "a_uplift", "hk_uplift", ah_ratio_key, "hk_flag"

        for i in [1]: # 3, 5, 10, 20
            x_cols.append(f"avg_{i}d_a_pct")
            x_cols.append(f"avg_{i}d_hk_pct")

        train_x_nd: np.ndarray = train_df.loc[:, x_cols].values
        train_y_nd: np.ndarray = train_df.loc[:, label_key].values
        test_x_nd: np.ndarray = test_df.loc[:, x_cols].values
        test_y_nd: np.ndarray = test_df.loc[:, label_key].values
        rule_y_nd: np.ndarray = test_df.loc[:, ah_ratio_key].values

        model = Ridge(alpha=1)
        model.fit(train_x_nd, train_y_nd)
        import ray
        ray.logger.info(f"dt={dt} w={model.coef_} b={model.intercept_}")
        pred_y_nd: np.ndarray = model.predict(test_x_nd)
        test_df.loc[:, pred_key] = pred_y_nd

        model_ic, _ = pearsonr(pred_y_nd, test_y_nd)
        model_ric, _ = spearmanr(pred_y_nd, test_y_nd)  # noqa
        rule_ic, _ = pearsonr(rule_y_nd, test_y_nd)
        rule_ric, _ = spearmanr(rule_y_nd, test_y_nd)  # noqa

        model_df = test_df.sort_values(by=pred_key, ascending=False)[:5]
        rule_df = test_df.sort_values(by=ah_ratio_key, ascending=False)[:5]

        result = {
            "dt": dt,
            "size": len(test_df),
            "model_ic": model_ic,
            "model_ric": model_ric,
            "rule_ic": rule_ic,
            "rule_ric": rule_ric,
            "rule_names": ",".join(rule_df.loc[:, "name"].tolist()),
            "rule_uplift": rule_df.loc[:, label_key].mean(),
            "model_names": ",".join(model_df.loc[:, "name"].tolist()),
            "model_uplift": model_df.loc[:, label_key].mean(),
            "all_uplift": test_y_nd.mean(),
        }

        block_size = 5
        block_cnt = round(len(test_df) / block_size)
        test_df_sorted = test_df.sort_values(by=pred_key, ascending=False)
        for i in range(block_size):
            result[f"p{i}_uplift"] = test_df_sorted[i * block_cnt: (i + 1) * block_cnt].loc[:, label_key].mean()
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
