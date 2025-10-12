"""
AH股特征标签宽表Op
负责生成特征和标签的大宽表：
1. 计算AH比价
2. 计算成交额比
3. 计算历史涨跌幅
4. 生成未来收益标签
支持日频和周频两种模式
"""
import os
from typing import Dict, List, Optional

import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.app import FlowLLMApp
from flowllm.context.service_context import C
from flowllm.op import BaseOp, BaseRayOp
from flowllm.utils.common_utils import find_dt_less_index, get_monday_fridays, next_friday_or_same

HISTORY_WINDOWS = [1, 3, 5, 10, 20]  # 历史涨跌幅窗口


@C.register_op(register_app="FlowLLM")
class AhFeatureTableOp(BaseRayOp):
    """生成AH股特征标签大宽表（父Op）"""

    def __init__(
        self,
        input_dir: str = "data/fixed",
        output_dir: str = "data/feature",
        use_open: bool = True,
        use_weekly: bool = False,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.use_open = use_open
        self.use_weekly = use_weekly

    def _ensure_output_dir(self) -> None:
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)

    def _load_ah_comparison(self) -> pd.DataFrame:
        """读取AH对比数据"""
        # 优先从fixed目录读取，否则从origin目录
        for dir_name in [self.input_dir, "data/origin"]:
            path = os.path.join(dir_name, "stk_ah_comparison.csv")
            if os.path.exists(path):
                df = pd.read_csv(path)
                ah_df = df.loc[df.trade_date == df.trade_date.max(), ["hk_code", "ts_code", "name"]].copy()
                logger.info(f"Loaded {len(ah_df)} AH pairs from {path}")
                return ah_df
        raise FileNotFoundError("stk_ah_comparison.csv not found")

    def _load_data_from_files(self) -> None:
        """从文件加载数据（支持独立运行）"""
        logger.info(f"Loading data from {self.input_dir}...")
        
        # 1. 读取AH对比数据
        ah_df = self._load_ah_comparison()
        
        # 2. 读取汇率比率
        forex_ratio_path = os.path.join(self.input_dir, "hk_forex_ratio.csv")
        hk_forex_df = pd.read_csv(forex_ratio_path, index_col=0)
        logger.info(f"Loaded forex ratio: {len(hk_forex_df)} rows")
        
        # 3. 读取股票数据
        stock_dict = {}
        a_date_counter = {}
        hk_date_counter = {}
        
        for record in tqdm(ah_df.to_dict(orient="records"), desc="Loading stocks"):
            hk_code, ts_code, name = record["hk_code"], record["ts_code"], record["name"]
            
            try:
                # 读取A股和HK股数据
                a_df = pd.read_csv(os.path.join(self.input_dir, f"daily_{ts_code}.csv"))
                hk_df = pd.read_csv(os.path.join(self.input_dir, f"hk_daily_{hk_code}.csv"))
                
                # 获取日期列表并对齐
                hk_dates = sorted(hk_df["trade_date"].unique())
                min_hk_date = min(hk_dates)
                a_dates = sorted([d for d in a_df["trade_date"].unique() if d >= min_hk_date])
                
                stock_dict[name] = {
                    "a_code": ts_code,
                    "hk_code": hk_code,
                    "a_org_stock_df": a_df,
                    "hk_org_stock_df": hk_df,
                    "hk_dt_list": hk_dates,
                    "a_dt_list": a_dates,
                }
                
                # 统计日期覆盖
                for dt in a_dates:
                    a_date_counter[dt] = a_date_counter.get(dt, 0) + 1
                for dt in hk_dates:
                    hk_date_counter[dt] = hk_date_counter.get(dt, 0) + 1
                
            except Exception as e:
                logger.warning(f"Failed to load {name} ({ts_code}/{hk_code}): {e}")
                continue
        
        logger.info(f"Loaded {len(stock_dict)} stock pairs")
        
        # 存入context
        self.context.ah_df = ah_df
        self.context.hk_forex_df = hk_forex_df
        self.context.stock_dict = stock_dict
        self.context.dt_a_list = sorted(a_date_counter.keys())
        self.context.dt_hk_list = sorted(hk_date_counter.keys())

    def _prepare_weekly_dates(self) -> None:
        """准备周频日期列表（每周最后一个交易日）"""
        weekly_dates = []
        monday_fridays = get_monday_fridays(self.context.dt_a_list[0], self.context.dt_a_list[-1])
        
        for monday, friday in monday_fridays:
            week_dates = [d for d in self.context.dt_a_list if monday <= str(d) <= friday]
            if week_dates:
                weekly_dates.append(week_dates[-1])  # 取本周最后一个交易日
        
        logger.info(f"Generated {len(weekly_dates)} weekly dates")
        self.context.dt_a_weekly_list = weekly_dates

    def execute(self) -> None:
        """执行特征生成"""
        self._ensure_output_dir()
        
        # 从文件加载数据
        self._load_data_from_files()
        
        # 设置参数到context
        self.context.use_open = self.use_open
        self.context.use_weekly = self.use_weekly
        
        # 选择日频或周频模式
        if self.use_weekly:
            self._prepare_weekly_dates()
            f_op = self.ops[1]  # AhWeeklyFeatureOp
            dt_list = self.context.dt_a_weekly_list
            cache_name = "feature_weekly.csv"
        else:
            f_op = self.ops[0]  # AhDailyFeatureOp
            dt_list = self.context.dt_a_list
            cache_name = "feature_daily.csv"
        
        mode = "weekly" if self.use_weekly else "daily"
        logger.info(f"Generating {mode} features for {len(dt_list)} dates")
        
        # 并行执行特征生成
        result = self.submit_and_join_parallel_op(op=f_op, dt=dt_list)
        
        # 合并并排序结果
        df = pd.DataFrame(result).sort_values(["dt", "code"])
        
        # 验证数据完整性
        nan_count = df.isnull().sum().sum()
        if nan_count > 0:
            logger.warning(f"Feature table has {nan_count} NaN values")
        
        # 保存特征表
        output_path = os.path.join(self.output_dir, cache_name)
        df.to_csv(output_path, index=False)
        logger.info(f"Saved {mode} features: {df.shape} to {output_path}")


class AhDailyFeatureOp(BaseOp):
    """生成日频特征（子Op）"""

    @staticmethod
    def _get_forex_ratio(dt: int, hk_forex_df: pd.DataFrame) -> Optional[float]:
        """获取指定日期的汇率比率"""
        forex_dates = [d for d in hk_forex_df.index if d < dt]
        if not forex_dates:
            return None
        forex_dt = forex_dates[find_dt_less_index(dt, forex_dates)]
        return hk_forex_df.loc[forex_dt, "close"]

    @staticmethod
    def _calculate_history_features(
        df: pd.DataFrame,
        dt_list: List[int],
        dt_index: int,
        windows: List[int] = HISTORY_WINDOWS
    ) -> Dict[str, float]:
        """计算历史涨跌幅特征"""
        features = {}
        for window in windows:
            start_idx = max(0, dt_index - (window - 1))
            date_slice = dt_list[start_idx: dt_index + 1]
            matched = df.loc[df.index.isin(date_slice), "pct_chg"]
            features[f"avg_{window}d"] = matched.mean() if len(matched) > 0 else 0
        return features

    @staticmethod
    def _calculate_future_return_open(
        df: pd.DataFrame,
        dt_list: List[int],
        dt_index: int,
        days_ahead: int = 2
    ) -> float:
        """使用开盘价计算未来收益（避免look-ahead bias）"""
        if dt_index >= len(dt_list) - days_ahead:
            return 0.0
        
        # 第一天：open -> close
        ratio = df.loc[dt_list[dt_index + 1], "close"] / df.loc[dt_list[dt_index + 1], "open"]
        
        # 后续天：累乘pct_chg
        for i in range(dt_index + 2, dt_index + days_ahead + 1):
            if i < len(dt_list):
                ratio *= (1 + df.loc[dt_list[i], "pct_chg"] / 100)
        
        return (ratio - 1) * 100

    def execute(self):
        result = []
        dt = self.context.dt
        use_open = self.context.use_open
        hk_forex_df = self.context.hk_forex_df
        
        # 获取汇率
        hk_forex_ratio = self._get_forex_ratio(dt, hk_forex_df)
        if hk_forex_ratio is None:
            logger.warning(f"No forex data for dt={dt}")
            return result

        for name, stock_info in self.context.stock_dict.items():
            a_dt_list = stock_info["a_dt_list"]
            if dt not in a_dt_list:
                continue

            hk_dt_list = stock_info["hk_dt_list"]
            dt_a_index = a_dt_list.index(dt)
            dt_hk_index = find_dt_less_index(dt, hk_dt_list)

            # 检查数据充足性
            if dt_a_index < 1 or dt_hk_index is None or dt_hk_index < 1:
                continue

            a_df = stock_info["a_org_stock_df"].set_index("trade_date")
            hk_df = stock_info["hk_org_stock_df"].set_index("trade_date")

            # 当前价格和成交额
            a_curr_dt = a_dt_list[dt_a_index]
            hk_curr_dt = hk_dt_list[dt_hk_index]
            
            current_a_close = a_df.loc[a_curr_dt, "close"]
            current_hk_close = hk_df.loc[hk_curr_dt, "close"]
            current_a_amount = a_df.loc[a_curr_dt, "amount"]
            current_hk_amount = hk_df.loc[hk_curr_dt, "amount"]

            # 计算未来收益标签
            if use_open:
                next_a_uplift = self._calculate_future_return_open(a_df, a_dt_list, dt_a_index, days_ahead=2)
                next_hk_uplift = self._calculate_future_return_open(hk_df, hk_dt_list, dt_hk_index, days_ahead=2)
            else:
                next_a_uplift = a_df.loc[a_dt_list[dt_a_index + 1], "pct_chg"] if dt_a_index < len(a_dt_list) - 1 else 0
                next_hk_uplift = hk_df.loc[hk_dt_list[dt_hk_index + 1], "pct_chg"] if dt_hk_index < len(hk_dt_list) - 1 else 0

            # 构建特征字典
            feature = {
                "dt": dt,
                "name": name,
                "code": f"{stock_info['a_code']}+{stock_info['hk_code']}",
                "current_a_close": current_a_close,
                "current_hk_close": current_hk_close,
                "hk_forex_ratio": hk_forex_ratio,
                "a_flag": 1,
                "hk_flag": 1,
                "a_uplift": a_df.loc[a_curr_dt, "pct_chg"],
                "hk_uplift": hk_df.loc[hk_curr_dt, "pct_chg"],
                "ah_amount": (current_hk_amount / current_a_amount - 1) if current_a_amount != 0 else 0,
                "ah_ratio": current_hk_close * hk_forex_ratio / current_a_close,
                "a_label": next_a_uplift,
                "hk_label": next_hk_uplift,
            }

            # 添加历史涨跌幅特征
            a_hist = self._calculate_history_features(a_df, a_dt_list, dt_a_index)
            hk_hist = self._calculate_history_features(hk_df, hk_dt_list, dt_hk_index)
            
            for window in HISTORY_WINDOWS:
                feature[f"avg_{window}d_a_pct"] = a_hist[f"avg_{window}d"]
                feature[f"avg_{window}d_hk_pct"] = hk_hist[f"avg_{window}d"]

            result.append(feature)

        return result


class AhWeeklyFeatureOp(BaseOp):
    """生成周频特征（子Op）"""

    @staticmethod
    def _calculate_weekly_return(df: pd.DataFrame, label_dates: List[int]) -> float:
        """计算周收益：第一天用开盘价，后续天累乘"""
        if not label_dates:
            return 0.0
        
        # 第一天：open -> close
        ratio = df.loc[label_dates[0], "close"] / df.loc[label_dates[0], "open"]
        
        # 后续天：累乘pct_chg
        for dt in label_dates[1:]:
            ratio *= (1 + df.loc[dt, "pct_chg"] / 100)
        
        return (ratio - 1) * 100

    def execute(self):
        result = []
        dt = self.context.dt
        use_open = self.context.use_open
        hk_forex_df = self.context.hk_forex_df
        
        if not use_open:
            raise ValueError("Weekly feature generation requires use_open=True")
        
        # 获取汇率
        hk_forex_ratio = AhDailyFeatureOp._get_forex_ratio(dt, hk_forex_df)
        if hk_forex_ratio is None:
            logger.warning(f"No forex data for dt={dt}")
            return result

        for name, stock_info in self.context.stock_dict.items():
            a_dt_list = stock_info["a_dt_list"]
            if dt not in a_dt_list:
                continue

            hk_dt_list = stock_info["hk_dt_list"]
            dt_a_index = a_dt_list.index(dt)
            dt_hk_index = find_dt_less_index(dt, hk_dt_list)

            # 检查数据充足性
            if dt_a_index < 1 or dt_hk_index is None or dt_hk_index < 1:
                continue

            # 计算下周日期范围（用于标签）
            start_dt = a_dt_list[dt_a_index + 1] if dt_a_index < len(a_dt_list) - 1 else dt
            end_dt = int(next_friday_or_same(str(start_dt)))
            label_dates = [d for d in a_dt_list if start_dt <= d <= end_dt]
            
            if not label_dates or start_dt > end_dt:
                continue

            a_df = stock_info["a_org_stock_df"].set_index("trade_date")
            hk_df = stock_info["hk_org_stock_df"].set_index("trade_date")

            # 当前价格和成交额
            a_curr_dt = a_dt_list[dt_a_index]
            hk_curr_dt = hk_dt_list[dt_hk_index]
            
            current_a_close = a_df.loc[a_curr_dt, "close"]
            current_hk_close = hk_df.loc[hk_curr_dt, "close"]
            current_a_amount = a_df.loc[a_curr_dt, "amount"]
            current_hk_amount = hk_df.loc[hk_curr_dt, "amount"]

            # 5日平均成交额
            a_5d_slice = a_dt_list[max(dt_a_index - 4, 0):dt_a_index + 1]
            hk_5d_slice = hk_dt_list[max(dt_hk_index - 4, 0):dt_hk_index + 1]
            current5_a_amount = a_df.loc[a_df.index.isin(a_5d_slice), "amount"].mean()
            current5_hk_amount = hk_df.loc[hk_df.index.isin(hk_5d_slice), "amount"].mean()

            # 计算周收益
            next_a_uplift = self._calculate_weekly_return(a_df, label_dates)

            # 构建特征字典
            feature = {
                "dt": dt,
                "name": name,
                "code": f"{stock_info['a_code']}+{stock_info['hk_code']}",
                "current_a_close": current_a_close,
                "current_hk_close": current_hk_close,
                "hk_forex_ratio": hk_forex_ratio,
                "a_flag": 1,
                "hk_flag": 1,
                "a_uplift": a_df.loc[a_curr_dt, "pct_chg"],
                "hk_uplift": hk_df.loc[hk_curr_dt, "pct_chg"],
                "ah_amount": (current_hk_amount / current_a_amount - 1) if current_a_amount != 0 else 0,
                "ah_amount5": (current5_hk_amount / current5_a_amount - 1) if current5_a_amount != 0 else 0,
                "ah_ratio": current_hk_close * hk_forex_ratio / current_a_close,
                "a_label": next_a_uplift,
                "hk_label": 0,  # 周频不计算HK的周收益
            }

            # 添加历史涨跌幅特征
            a_hist = AhDailyFeatureOp._calculate_history_features(a_df, a_dt_list, dt_a_index)
            hk_hist = AhDailyFeatureOp._calculate_history_features(hk_df, hk_dt_list, dt_hk_index)
            
            for window in HISTORY_WINDOWS:
                feature[f"avg_{window}d_a_pct"] = a_hist[f"avg_{window}d"]
                feature[f"avg_{window}d_hk_pct"] = hk_hist[f"avg_{window}d"]

            result.append(feature)

        return result


def main(use_weekly: bool = False, use_open: bool = True):
    """生成AH股特征标签"""
    with FlowLLMApp(load_default_config=True) as app:
        app.service_config.ray_max_workers = 8
        
        op = (
            AhFeatureTableOp(
                input_dir="data/fixed",
                output_dir="data/feature",
                use_open=use_open,
                use_weekly=use_weekly
            )
            << AhDailyFeatureOp()
            << AhWeeklyFeatureOp()
        )
        op.call()


if __name__ == "__main__":
    # 生成日频特征
    # main(use_weekly=False, use_open=True)
    
    # 生成周频特征
    main(use_weekly=True, use_open=True)
