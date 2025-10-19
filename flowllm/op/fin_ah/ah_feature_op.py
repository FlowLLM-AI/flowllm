"""
AH股特征标签宽表Op
负责生成特征和标签的大宽表：
1. 计算AH比价
2. 计算成交额比
3. 计算历史涨跌幅
4. 计算A/H涨跌幅的差值
5. 计算A/H成交额的比值
6. 生成未来收益标签
支持日频和周频两种模式
"""
import os
from typing import Dict, List, Optional

import pandas as pd
import ray
from loguru import logger

from flowllm.app import FlowLLMApp
from flowllm.context.service_context import C
from flowllm.op import BaseOp, BaseRayOp
from flowllm.utils.common_utils import find_dt_less_index, get_monday_fridays, next_friday_or_same

HISTORY_WINDOWS = [1, 3, 5, 10, 15, 20, 30, 60]  # 历史涨跌幅和成交额窗口


@C.register_op(register_app="FlowLLM")
class AhFeatureTableOp(BaseRayOp):
    """生成AH股特征标签大宽表（父Op）"""

    def __init__(self,
                 input_dir: str = "data/fixed",
                 output_dir: str = "data/feature",
                 use_weekly: bool = False,
                 **kwargs):

        super().__init__(**kwargs)
        self.input_dir = input_dir
        self.output_dir = output_dir
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

        # 使用列表推导式而不是tqdm迭代器
        records = ah_df.to_dict(orient="records")
        total = len(records)
        logger.info(f"Loading {total} stock pairs...")

        for idx, record in enumerate(records):
            hk_code, ts_code, name = record["hk_code"], record["ts_code"], record["name"]

            if (idx + 1) % 10 == 0:
                logger.info(f"Loading progress: {idx + 1}/{total}")
            
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
                logger.exception(f"Failed to load {name} ({ts_code}/{hk_code}): {e}")
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
                week_dates = sorted(week_dates)
                weekly_dates.append(week_dates[-1])  # 取本周最后一个交易日
        
        logger.info(f"Generated {len(weekly_dates)} weekly dates")
        self.context.dt_a_weekly_list = weekly_dates

    def execute(self) -> None:
        """执行特征生成"""
        self._ensure_output_dir()
        
        # 从文件加载数据
        self._load_data_from_files()
        
        # 设置参数到context
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
    def get_forex_ratio(dt: int, hk_forex_df: pd.DataFrame) -> Optional[float]:
        """获取指定日期的汇率比率"""
        forex_dates = [d for d in hk_forex_df.index if d < dt]
        if not forex_dates:
            return None

        forex_dt = forex_dates[find_dt_less_index(dt, forex_dates)]
        return hk_forex_df.loc[forex_dt, "close"]

    @staticmethod
    def calculate_history_features(df: pd.DataFrame,
                                   dt_list: List[int],
                                   dt_index: int,
                                   windows: List[int] = None) -> Dict[str, float]:

        """计算历史累积涨跌幅特征（复合收益率）"""
        if windows is None:
            windows = HISTORY_WINDOWS

        features = {}
        for window in windows:
            start_idx = max(0, dt_index - (window - 1))
            date_slice = dt_list[start_idx: dt_index + 1]
            matched = df.loc[df.index.isin(date_slice), "pct_chg"]

            # 计算累积收益率：(1 + r1) * (1 + r2) * ... - 1
            if len(matched) > 0:
                cumulative_return = 1.0
                for pct in matched:
                    cumulative_return *= (1 + pct / 100)
                features[f"avg_{window}d"] = (cumulative_return - 1) * 100
            else:
                features[f"avg_{window}d"] = 0
        return features

    @staticmethod
    def calculate_history_amount_features(df: pd.DataFrame,
                                          dt_list: List[int],
                                          dt_index: int,
                                          windows: List[int] = None) -> Dict[str, float]:
        """计算历史成交额特征"""
        if windows is None:
            windows = HISTORY_WINDOWS

        features = {}
        for window in windows:
            start_idx = max(0, dt_index - (window - 1))
            date_slice = dt_list[start_idx: dt_index + 1]
            matched = df.loc[df.index.isin(date_slice), "amount"]
            features[f"avg_{window}d_amount"] = matched.mean() if len(matched) > 0 else 0
        return features

    @staticmethod
    def _calculate_single_day_uplift(
        df: pd.DataFrame,
        dt_list: List[int],
        dt_index: int,
        day_offset: int = 1
    ) -> float:
        """计算单日uplift：从某天开盘到下一天开盘的收益
        
        Args:
            df: 股票数据
            dt_list: 日期列表
            dt_index: 当前日期索引
            day_offset: 从当前日期往后偏移几天（1表示明天开盘到后天开盘）
        
        Returns:
            收益率（百分比）
        """
        start_idx = dt_index + day_offset
        end_idx = dt_index + day_offset + 1

        if start_idx >= len(dt_list) or end_idx >= len(dt_list):
            return 0.0

        start_open = df.loc[dt_list[start_idx], "open"]
        end_open = df.loc[dt_list[end_idx], "open"]

        return (end_open / start_open - 1) * 100

    @staticmethod
    def _calculate_avg_future_uplift(
            df: pd.DataFrame,
            dt_list: List[int],
            dt_index: int,
            n_days: int = 5
    ) -> float:
        """计算未来N天的平均uplift（累积收益率除以天数）
        
        Args:
            df: 股票数据
            dt_list: 日期列表
            dt_index: 当前日期索引
            n_days: 未来N天
        
        Returns:
            未来N天累积uplift除以天数
        """
        # 计算累积收益率：(1 + r1) * (1 + r2) * ... * (1 + rN) - 1
        cumulative_return = 1.0
        valid_days = 0
        
        for i in range(1, n_days + 1):
            if dt_index + i + 1 >= len(dt_list):
                break
            
            uplift = AhDailyFeatureOp._calculate_single_day_uplift(df, dt_list, dt_index, day_offset=i)
            cumulative_return *= (1 + uplift / 100)
            valid_days += 1
        
        if valid_days == 0:
            return 0.0
        
        # 累积收益率除以实际天数
        total_return = (cumulative_return - 1) * 100
        return total_return / valid_days

    def execute(self):
        result = []
        dt = self.context.dt
        hk_forex_df = self.context.hk_forex_df
        
        # 获取汇率
        hk_forex_ratio = self.get_forex_ratio(dt, hk_forex_df)
        if hk_forex_ratio is None:
            raise RuntimeError(f"No forex data for dt={dt}")

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

            # 计算uplift：明天开盘到后天开盘的涨跌幅
            next_a_uplift = self._calculate_single_day_uplift(a_df, a_dt_list, dt_a_index, day_offset=1)

            # 计算多个label：未来1/2/3/4/5天uplift的平均值
            labels = {}
            for n_days in [1, 2, 3, 4, 5]:
                labels[f"a_label_{n_days}d"] = self._calculate_avg_future_uplift(a_df, a_dt_list, dt_a_index,
                                                                                 n_days=n_days)

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
                "ah_ratio": current_hk_close * hk_forex_ratio / current_a_close,
                "a_label": labels["a_label_5d"],  # 保持向后兼容，默认使用5天
                "uplift": next_a_uplift,
            }

            # 添加多个label列
            feature.update(labels)

            # 添加历史涨跌幅特征
            a_hist = self.calculate_history_features(a_df, a_dt_list, dt_a_index)
            hk_hist = self.calculate_history_features(hk_df, hk_dt_list, dt_hk_index)
            
            for window in HISTORY_WINDOWS:
                feature[f"avg_{window}d_a_pct"] = a_hist[f"avg_{window}d"]
                feature[f"avg_{window}d_hk_pct"] = hk_hist[f"avg_{window}d"]
                # 添加涨跌幅的差值（A股涨跌幅 - H股涨跌幅）
                feature[f"avg_{window}d_ah_pct_diff"] = a_hist[f"avg_{window}d"] - hk_hist[f"avg_{window}d"]

            # 添加历史成交额特征
            a_amount_hist = self.calculate_history_amount_features(a_df, a_dt_list, dt_a_index)
            hk_amount_hist = self.calculate_history_amount_features(hk_df, hk_dt_list, dt_hk_index)

            for window in HISTORY_WINDOWS:
                feature[f"avg_{window}d_a_amount"] = a_amount_hist[f"avg_{window}d_amount"]
                feature[f"avg_{window}d_hk_amount"] = hk_amount_hist[f"avg_{window}d_amount"]
                # 添加成交额的比值（H股成交额 / A股成交额）
                a_amount = a_amount_hist[f"avg_{window}d_amount"]
                feature[f"avg_{window}d_ah_amount_ratio"] = (
                    hk_amount_hist[f"avg_{window}d_amount"] / a_amount if a_amount != 0 else 0
                )

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
        hk_forex_df = self.context.hk_forex_df

        # 获取汇率
        hk_forex_ratio = AhDailyFeatureOp.get_forex_ratio(dt, hk_forex_df)
        if hk_forex_ratio is None:
            ray.logger.warning(f"No forex data for dt={dt}")
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

            # 计算下周收益：从下周开盘到下周收盘的涨跌幅
            # label和uplift保持一致（用于训练和回测）
            next_week_return = self._calculate_weekly_return(a_df, label_dates)

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
                "ah_ratio": current_hk_close * hk_forex_ratio / current_a_close,
                "a_label": next_week_return,
                "uplift": next_week_return,
            }

            # 添加历史涨跌幅特征
            a_hist = AhDailyFeatureOp.calculate_history_features(a_df, a_dt_list, dt_a_index)
            hk_hist = AhDailyFeatureOp.calculate_history_features(hk_df, hk_dt_list, dt_hk_index)

            for window in HISTORY_WINDOWS:
                feature[f"avg_{window}d_a_pct"] = a_hist[f"avg_{window}d"]
                feature[f"avg_{window}d_hk_pct"] = hk_hist[f"avg_{window}d"]
                # 添加涨跌幅的差值（A股涨跌幅 - H股涨跌幅）
                feature[f"avg_{window}d_ah_pct_diff"] = a_hist[f"avg_{window}d"] - hk_hist[f"avg_{window}d"]

            # 添加历史成交额特征
            a_amount_hist = AhDailyFeatureOp.calculate_history_amount_features(a_df, a_dt_list, dt_a_index)
            hk_amount_hist = AhDailyFeatureOp.calculate_history_amount_features(hk_df, hk_dt_list, dt_hk_index)

            for window in HISTORY_WINDOWS:
                feature[f"avg_{window}d_a_amount"] = a_amount_hist[f"avg_{window}d_amount"]
                feature[f"avg_{window}d_hk_amount"] = hk_amount_hist[f"avg_{window}d_amount"]
                # 添加成交额的比值（H股成交额 / A股成交额）
                a_amount = a_amount_hist[f"avg_{window}d_amount"]
                feature[f"avg_{window}d_ah_amount_ratio"] = (
                    hk_amount_hist[f"avg_{window}d_amount"] / a_amount if a_amount != 0 else 0
                )

            result.append(feature)

        return result


def main(use_weekly: bool):
    """生成AH股特征标签"""
    with FlowLLMApp(load_default_config=True) as app:
        app.service_config.ray_max_workers = 8

        op = AhFeatureTableOp(input_dir="data/fixed",
                              output_dir="data/feature",
                              use_weekly=use_weekly) << AhDailyFeatureOp() << AhWeeklyFeatureOp()


        op.call()


if __name__ == "__main__":
    # 生成日频特征
    main(use_weekly=False)
    
    # 生成周频特征
    # main(use_weekly=True)
