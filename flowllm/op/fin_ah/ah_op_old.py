from typing import List

import numpy as np
import pandas as pd
from loguru import logger
from scipy.stats import spearmanr, pearsonr
from sklearn.linear_model import Ridge
from tqdm import tqdm

from flowllm.context.service_context import C
from flowllm.op import BaseOp, BaseRayOp
from flowllm.utils.common_utils import find_dt_less_index, get_monday_fridays, next_friday_or_same
from flowllm.utils.plot_utils import plot_figure
from flowllm.utils.tushare_client import TushareClient


@C.register_op(register_app="FlowLLM")
class AhOp(BaseRayOp):

    def __init__(self,
                 enable_cache: bool = True,
                 cache_expire_hours: float = 24,
                 max_samples: int = 512,
                 use_open: bool = True,
                 use_weekly: bool = True,
                 **kwargs):
        super().__init__(enable_cache=enable_cache, cache_expire_hours=cache_expire_hours, **kwargs)
        self.max_samples: int = max_samples
        self.use_open: bool = use_open
        self.use_weekly: bool = use_weekly
        self.ts_client = TushareClient()

    @staticmethod
    def fix_df(df: pd.DataFrame) -> pd.DataFrame:
        flag_index = (df["pre_close"].isna()) | (df["pre_close"] == 0.0)
        df.loc[flag_index, "pre_close"] = df["close"].shift(-1)
        df.loc[flag_index, "change"] = df["close"] - df["pre_close"]
        df.loc[flag_index, "pct_chg"] = (df["close"] / df["pre_close"] - 1) * 100
        df = df[:-1].copy()
        return df

    def prepare_raw_data(self):
        logger.info("start")
        df = self.ts_client.request(api_name="stk_ah_comparison")
        ah_df = df.loc[df.trade_date == df.trade_date.max(), ["hk_code", "ts_code", "name"]]
        self.context.ah_df = ah_df
        logger.info(f"ah_df=\n{ah_df}")

        df_cnh: pd.DataFrame = self.ts_client.request(api_name="fx_daily", ts_code='USDCNH.FXCM')
        df_hkd: pd.DataFrame = self.ts_client.request(api_name="fx_daily", ts_code='USDHKD.FXCM')
        df_cnh = df_cnh.loc[df_cnh.trade_date > 20150101, ["trade_date", "bid_close"]].set_index("trade_date").rename(
            columns={"bid_close": "cnh_close"})
        df_hkd = df_hkd.loc[df_hkd.trade_date > 20150101, ["trade_date", "bid_close"]].set_index("trade_date").rename(
            columns={"bid_close": "hkd_close"})
        hk_forex_df = df_cnh.join(df_hkd).ffill()
        nan_size = hk_forex_df.isnull().sum().sum()
        assert nan_size == 0, f"hk_forex_df has null. size={nan_size}"
        hk_forex_df.loc[:, "close"] = hk_forex_df.loc[:, "cnh_close"] / hk_forex_df.loc[:, "hkd_close"]
        self.context.hk_forex_df = hk_forex_df

        self.context.stock_dict = {}
        a_dt_size_dict = {}
        hk_dt_size_dict = {}
        for line in tqdm(ah_df.to_dict(orient="records")):
            hk_code = line["hk_code"]
            ts_code = line["ts_code"]
            name = line["name"]

            # logger.info(f"hk_code={hk_code} ts_code={ts_code} name={name}")
            a_org_stock_df = self.ts_client.request(api_name="daily", ts_code=ts_code)
            hk_org_stock_df = self.ts_client.request(api_name="hk_daily", ts_code=hk_code)
            hk_org_stock_df = self.fix_df(hk_org_stock_df)

            a_org_stock_df = a_org_stock_df.loc[a_org_stock_df.trade_date > 20160101, :]
            hk_org_stock_df = hk_org_stock_df.loc[hk_org_stock_df.trade_date > 20160101, :]
            self.cache.save(f"{hk_code}", hk_org_stock_df)

            nan_size = a_org_stock_df.isnull().sum().sum()
            assert nan_size == 0, f"{name}.{ts_code}.a_org_stock_df has null. size={nan_size}"

            nan_size = hk_org_stock_df.isnull().sum().sum()
            assert nan_size == 0, f"{name}.{hk_code}.hk_org_stock_df has null. size={nan_size}"

            hk_dt_list = sorted(hk_org_stock_df.loc[:, "trade_date"].unique())
            min_hk_dt = min(hk_dt_list)
            a_dt_list = sorted(a_org_stock_df.loc[:, "trade_date"].unique())
            a_dt_list = [x for x in a_dt_list if x >= min_hk_dt]

            self.context.stock_dict[name] = {
                "a_code": ts_code,
                "hk_code": hk_code,
                "a_org_stock_df": a_org_stock_df,
                "hk_org_stock_df": hk_org_stock_df,
                "hk_dt_list": hk_dt_list,
                "a_dt_list": a_dt_list,
            }

            for dt in a_dt_list:
                if dt not in a_dt_size_dict:
                    a_dt_size_dict[dt] = 0
                a_dt_size_dict[dt] += 1

            for dt in hk_dt_list:
                if dt not in hk_dt_size_dict:
                    hk_dt_size_dict[dt] = 0
                hk_dt_size_dict[dt] += 1

        for dt, cnt in sorted(a_dt_size_dict.items(), key=lambda x: x[0]):
            logger.info(f"{dt}: {cnt}")

        for dt, cnt in sorted(hk_dt_size_dict.items(), key=lambda x: x[0]):
            logger.info(f"{dt}: {cnt}")

        self.context.dt_a_list = sorted(a_dt_size_dict.keys())
        self.context.dt_hk_list = sorted(hk_dt_size_dict.keys())

        if self.use_weekly:
            dt_a_weekly_list = []
            monday_friday_list: List[List[str]] = get_monday_fridays(self.context.dt_a_list[0],
                                                                     self.context.dt_a_list[-1])
            for monday_friday in monday_friday_list:
                monday = str(monday_friday[0])
                friday = str(monday_friday[1])
                dt_a_weekly = [x for x in self.context.dt_a_list if monday <= str(x) <= friday]
                if dt_a_weekly:
                    dt_a_weekly_list.append(dt_a_weekly[-1])
            logger.info(f"dt_a_weekly_list={dt_a_weekly_list}")
            self.context.dt_a_weekly_list = dt_a_weekly_list


    def prepare_feature_data(self):
        self.context.use_open = self.use_open
        self.context.use_weekly = self.use_weekly

        if self.use_weekly:
            f_op = self.ops[1]
            dt_list = self.context.dt_a_weekly_list
            cache_name = "feature_w_df"
        else:
            f_op = self.ops[0]
            dt_list = self.context.dt_a_list
            cache_name = "feature_df"

        result = self.submit_and_join_parallel_op(op=f_op, dt=dt_list)

        df = pd.DataFrame(result).sort_values(["dt", "code"])
        self.cache.save(cache_name, df)

    def prepare_backtest(self):
        logger.info("start backtest")
        b_op = self.ops[2]
        self.context.max_samples = self.max_samples
        self.context.use_open = self.use_open

        if self.use_weekly:
            cache_name = "feature_w_df"
        else:
            cache_name = "feature_df"
        feature_df = self.cache.load(cache_name)
        nan_size = feature_df.isnull().sum().sum()
        assert nan_size == 0, f"feature_df has null. size={nan_size}"

        self.context.feature_df = feature_df
        logger.info(f"feature_df.shape={feature_df.shape}")
        dt_a_list = sorted(set(feature_df.loc[feature_df.a_flag == 1, "dt"]))
        self.context.dt_a_list = dt_a_list
        logger.info(f"dt_a_list={dt_a_list[0]}...{dt_a_list[-1]} size={len(dt_a_list)}")

        dts = [x for x in dt_a_list if x >= 20200101]
        result = self.submit_and_join_parallel_op(op=b_op, dt=dts)

        df = pd.DataFrame(result).sort_values(["dt"])
        self.cache.save("backtest_df", df)

        for key in ["model_ic", "model_ric", "rule_ic", "rule_ric"]:
            logger.info(f"{key} mean={df[key].mean()} std={df[key].std()}")

        strategy_list = [x for x in df.columns.tolist() if "_uplift" in x]
        logger.info(f"find strategy_list={strategy_list}")

        plot_dict = {x: [x / 100 for x in df.loc[:, x].tolist()] for x in strategy_list}
        plot_figure(plot_dict, output_path="ah_strategy.pdf", xs=[str(x) for x in dts], ticks_gap=90)

    def execute(self):
        self.prepare_raw_data()
        self.prepare_feature_data()

        self.prepare_backtest()


class AhFeatureOp(BaseOp):

    def execute(self):
        # actor_index = self.context.actor_index
        result = []
        dt = self.context.dt
        use_open: bool = self.context.use_open
        hk_forex_df = self.context.hk_forex_df
        # 晚一天时间
        hk_forex_dt_list = [x for x in sorted(hk_forex_df.index.unique()) if x < dt]
        hk_forex_dt = hk_forex_dt_list[find_dt_less_index(dt, hk_forex_dt_list)]
        hk_forex_ratio = hk_forex_df.loc[hk_forex_dt, "close"]

        for name, stock_info in self.context.stock_dict.items():
            t_result = {
                "dt": dt,
                "name": name,
                "code": stock_info["a_code"] + "+" + stock_info["hk_code"],
            }

            a_org_stock_df = stock_info["a_org_stock_df"].set_index("trade_date")
            hk_org_stock_df = stock_info["hk_org_stock_df"].set_index("trade_date")

            a_dt_list = stock_info["a_dt_list"]
            if dt not in a_dt_list:
                continue

            hk_dt_list = stock_info["hk_dt_list"]

            dt_a_index = a_dt_list.index(dt)
            dt_hk_index = find_dt_less_index(dt, hk_dt_list)

            if dt_a_index is None or len(a_dt_list[:dt_a_index + 1]) < 2:
                continue

            if dt_hk_index is None or len(hk_dt_list[:dt_hk_index + 1]) < 2:
                continue

            current_a_close = a_org_stock_df.loc[a_dt_list[dt_a_index], "close"]
            current_hk_close = hk_org_stock_df.loc[hk_dt_list[dt_hk_index], "close"]

            current_a_amount = a_org_stock_df.loc[a_dt_list[dt_a_index], "amount"]
            current_hk_amount = hk_org_stock_df.loc[hk_dt_list[dt_hk_index], "amount"]

            current_a_uplift = a_org_stock_df.loc[a_dt_list[dt_a_index], "pct_chg"]
            current_hk_uplift = hk_org_stock_df.loc[hk_dt_list[dt_hk_index], "pct_chg"]

            if use_open:
                if dt_a_index < len(a_dt_list) - 2:
                    # next_a_index = dt_a_index + 2
                    t1_open_close_ratio = a_org_stock_df.loc[a_dt_list[dt_a_index + 1], "close"] / a_org_stock_df.loc[
                        a_dt_list[dt_a_index + 1], "open"]
                    t2_open_close_ratio = a_org_stock_df.loc[a_dt_list[dt_a_index + 2], "close"] / a_org_stock_df.loc[
                        a_dt_list[dt_a_index + 2], "open"]
                    next_a_uplift = a_org_stock_df.loc[a_dt_list[dt_a_index + 2], "pct_chg"]
                    next_a_uplift = ((1 + next_a_uplift / 100) / t2_open_close_ratio * t1_open_close_ratio - 1) * 100

                else:
                    # next_a_index = dt_a_index
                    next_a_uplift = 0

                if dt_hk_index < len(hk_dt_list) - 2:
                    next_hk_index = dt_hk_index + 2
                    t1_open_close_ratio = hk_org_stock_df.loc[hk_dt_list[dt_hk_index + 1], "close"] / \
                                          hk_org_stock_df.loc[hk_dt_list[dt_hk_index + 1], "open"]
                    t2_open_close_ratio = hk_org_stock_df.loc[hk_dt_list[dt_hk_index + 2], "close"] / \
                                          hk_org_stock_df.loc[hk_dt_list[dt_hk_index + 2], "open"]
                    next_hk_uplift = hk_org_stock_df.loc[hk_dt_list[next_hk_index], "pct_chg"]
                    next_hk_uplift = ((1 + next_hk_uplift / 100) / t2_open_close_ratio * t1_open_close_ratio - 1) * 100

                else:
                    # next_hk_index = dt_hk_index
                    next_hk_uplift = 0

            else:
                if dt_a_index < len(a_dt_list) - 1:
                    next_a_index = dt_a_index + 1
                else:
                    next_a_index = dt_a_index
                next_a_uplift = a_org_stock_df.loc[a_dt_list[next_a_index], "pct_chg"]

                if dt_hk_index < len(hk_dt_list) - 1:
                    next_hk_index = dt_hk_index + 1
                else:
                    next_hk_index = dt_hk_index
                next_hk_uplift = hk_org_stock_df.loc[hk_dt_list[next_hk_index], "pct_chg"]

            t_result["current_hk_close"] = current_hk_close
            t_result["current_a_close"] = current_a_close
            t_result["hk_forex_ratio"] = hk_forex_ratio

            t_result["a_flag"] = 1 if dt in a_dt_list else 0
            t_result["hk_flag"] = 1 if dt in hk_dt_list else 0

            t_result["a_uplift"] = current_a_uplift
            t_result["hk_uplift"] = current_hk_uplift

            for i in [1, 3, 5, 10, 20]:
                a_start_idx = max(0, dt_a_index - (i - 1))
                hk_start_idx = max(0, dt_hk_index - (i - 1))

                a_date_slice = a_dt_list[a_start_idx: dt_a_index + 1]
                hk_date_slice = hk_dt_list[hk_start_idx: dt_hk_index + 1]

                a_matched = hk_org_stock_df.loc[hk_org_stock_df.index.isin(a_date_slice), "pct_chg"]
                hk_matched = hk_org_stock_df.loc[hk_org_stock_df.index.isin(hk_date_slice), "pct_chg"]

                t_result[f"avg_{i}d_a_pct"] = a_matched.mean() if len(a_matched) > 0 else 0
                t_result[f"avg_{i}d_hk_pct"] = hk_matched.mean() if len(hk_matched) > 0 else 0

            t_result["ah_amount"] = (current_hk_amount / current_a_amount - 1) if current_a_amount != 0 else 0
            t_result["ah_ratio"] = current_hk_close * hk_forex_ratio / current_a_close

            t_result["a_label"] = next_a_uplift
            t_result["hk_label"] = next_hk_uplift

            result.append(t_result)

        return result


class AhWeeklyFeatureOp(BaseOp):

    def execute(self):
        # actor_index = self.context.actor_index
        result = []
        dt = self.context.dt

        use_open: bool = self.context.use_open
        hk_forex_df = self.context.hk_forex_df
        # 晚一天时间
        hk_forex_dt_list = [x for x in sorted(hk_forex_df.index.unique()) if x < dt]
        hk_forex_dt = hk_forex_dt_list[find_dt_less_index(dt, hk_forex_dt_list)]
        hk_forex_ratio = hk_forex_df.loc[hk_forex_dt, "close"]

        for name, stock_info in self.context.stock_dict.items():
            t_result = {
                "dt": dt,
                "name": name,
                "code": stock_info["a_code"] + "+" + stock_info["hk_code"],
            }

            a_org_stock_df = stock_info["a_org_stock_df"].set_index("trade_date")
            hk_org_stock_df = stock_info["hk_org_stock_df"].set_index("trade_date")

            a_dt_list = stock_info["a_dt_list"]
            if dt not in a_dt_list:
                continue

            ##########
            dt_a_index: int = a_dt_list.index(dt)
            if dt_a_index != len(a_dt_list) - 1:
                start_dt = a_dt_list[dt_a_index + 1]
            else:
                start_dt = dt

            end_dt = next_friday_or_same(str(start_dt))
            label_dts = [x for x in a_dt_list if int(start_dt) <= x <= int(end_dt)]
            end_dt = label_dts[-1]
            assert start_dt <= end_dt, f"{name} dt={dt} start_dt={start_dt} > end_dt={end_dt}"
            assert len(label_dts) >= 1

            ##########

            hk_dt_list = stock_info["hk_dt_list"]

            dt_hk_index = find_dt_less_index(dt, hk_dt_list)

            if dt_a_index is None or len(a_dt_list[:dt_a_index + 1]) < 2:
                continue

            if dt_hk_index is None or len(hk_dt_list[:dt_hk_index + 1]) < 2:
                continue

            current_a_close = a_org_stock_df.loc[a_dt_list[dt_a_index], "close"]
            current_hk_close = hk_org_stock_df.loc[hk_dt_list[dt_hk_index], "close"]

            current_a_amount = a_org_stock_df.loc[a_dt_list[dt_a_index], "amount"]
            current_hk_amount = hk_org_stock_df.loc[hk_dt_list[dt_hk_index], "amount"]

            current5_a_amount = a_org_stock_df.loc[a_dt_list[max(dt_a_index - 4, 0):dt_a_index + 1], "amount"].mean()
            current5_hk_amount = hk_org_stock_df.loc[hk_dt_list[max(dt_hk_index - 4, 0):dt_hk_index + 1], "amount"].mean()

            current_a_uplift = a_org_stock_df.loc[a_dt_list[dt_a_index], "pct_chg"]
            current_hk_uplift = hk_org_stock_df.loc[hk_dt_list[dt_hk_index], "pct_chg"]

            assert use_open
            next_a_uplift = a_org_stock_df.loc[int(label_dts[0]), "close"] / a_org_stock_df.loc[
                int(label_dts[0]), "open"]
            for x_dt in label_dts[1:]:
                next_a_uplift *= (1 + a_org_stock_df.loc[int(x_dt), "pct_chg"] / 100)
            next_a_uplift = (next_a_uplift - 1) * 100

            next_hk_uplift = 0

            t_result["current_hk_close"] = current_hk_close
            t_result["current_a_close"] = current_a_close
            t_result["hk_forex_ratio"] = hk_forex_ratio

            t_result["a_flag"] = 1 if dt in a_dt_list else 0
            t_result["hk_flag"] = 1 if dt in hk_dt_list else 0

            t_result["a_uplift"] = current_a_uplift
            t_result["hk_uplift"] = current_hk_uplift

            for i in [1, 3, 5, 10, 20]:
                a_start_idx = max(0, dt_a_index - (i - 1))
                hk_start_idx = max(0, dt_hk_index - (i - 1))

                a_date_slice = a_dt_list[a_start_idx: dt_a_index + 1]
                hk_date_slice = hk_dt_list[hk_start_idx: dt_hk_index + 1]

                a_matched = hk_org_stock_df.loc[hk_org_stock_df.index.isin(a_date_slice), "pct_chg"]
                hk_matched = hk_org_stock_df.loc[hk_org_stock_df.index.isin(hk_date_slice), "pct_chg"]

                t_result[f"avg_{i}d_a_pct"] = a_matched.mean() if len(a_matched) > 0 else 0
                t_result[f"avg_{i}d_hk_pct"] = hk_matched.mean() if len(hk_matched) > 0 else 0

            t_result["ah_amount"] = (current_hk_amount / current_a_amount - 1) if current_a_amount != 0 else 0
            t_result["ah_amount5"] = (current5_hk_amount / current5_a_amount - 1) if current5_a_amount != 0 else 0
            t_result["ah_ratio"] = current_hk_close * hk_forex_ratio / current_a_close

            t_result["a_label"] = next_a_uplift
            t_result["hk_label"] = next_hk_uplift

            result.append(t_result)

        return result


class AhBacktestOp(BaseOp):

    def execute(self):
        dt = self.context.dt
        feature_df: pd.DataFrame = self.context.feature_df
        max_samples = self.context.max_samples
        train_dt_a_list: List[str] = [x for x in self.context.dt_a_list if x < dt][-max_samples:-1]

        train_df: pd.DataFrame = feature_df.loc[feature_df.dt.isin(train_dt_a_list)]
        test_df: pd.DataFrame = feature_df.loc[feature_df.dt == dt].copy()  # Fix: 使用.copy()避免SettingWithCopyWarning

        ah_ratio_key = "ah_ratio"
        label_key = "a_label"
        pred_key = "pred_y_nd"
        # dt,name,code,current_hk_close,current_a_close,hk_forex_ratio,a_flag,hk_flag,a_uplift,hk_uplift,ah_amount,ah_ratio,a_label,hk_label
        x_cols = [ah_ratio_key, "ah_amount5"]  #, "ah_amount" , ah_ratio_key, "hk_flag"

        for i in [20]:  # 3, 5, 10, 20
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

        block_size = 10
        block_cnt = round(len(test_df) / block_size)
        test_df_sorted = test_df.sort_values(by=pred_key, ascending=False)
        # test_df_sorted = test_df.sort_values(by=ah_ratio_key, ascending=False)
        for i in range(block_size):
            result[f"p{i}_uplift"] = test_df_sorted[i * block_cnt: (i + 1) * block_cnt].loc[:, label_key].mean()
        return result

def main():
    from flowllm.app import FlowLLMApp
    with FlowLLMApp(load_default_config=True) as app:
        app.service_config.ray_max_workers = 8

        op = AhOp()
        op = op << AhFeatureOp() << AhWeeklyFeatureOp() << AhBacktestOp()
        print(op.call())


if __name__ == "__main__":
    main()
