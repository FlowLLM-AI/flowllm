"""
AH股特征标签宽表Op
负责生成特征和标签的大宽表：
1. 计算AH比价
2. 计算成交额比
3. 计算历史涨跌幅
4. 生成未来收益标签
支持日频和周频两种模式
"""
from typing import List
import os
import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.context.service_context import C
from flowllm.op import BaseOp, BaseRayOp
from flowllm.utils.common_utils import find_dt_less_index, get_monday_fridays, next_friday_or_same


@C.register_op(register_app="FlowLLM")
class AhFeatureTableOp(BaseRayOp):
    """生成AH股特征标签大宽表（父Op）"""

    def __init__(self,
                 input_dir: str = "data/fixed",
                 output_dir: str = "data/feature",
                 use_open: bool = True,
                 use_weekly: bool = False,
                 **kwargs):
        super().__init__(**kwargs)
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.use_open = use_open
        self.use_weekly = use_weekly

    def _ensure_output_dir(self):
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)

    def _load_data_from_files(self):
        """从文件加载数据（支持独立运行）"""
        logger.info(f"Loading data from {self.input_dir}...")
        
        # 1. 读取AH对比数据
        ah_comparison_path = os.path.join(self.input_dir, "stk_ah_comparison.csv")
        if not os.path.exists(ah_comparison_path):
            # 如果fixed目录没有，尝试从origin目录读取
            ah_comparison_path = os.path.join("data/origin", "stk_ah_comparison.csv")
        
        df = pd.read_csv(ah_comparison_path)
        ah_df = df.loc[df.trade_date == df.trade_date.max(), ["hk_code", "ts_code", "name"]]
        logger.info(f"Loaded {len(ah_df)} AH pairs")
        
        # 2. 读取汇率比率
        forex_ratio_path = os.path.join(self.input_dir, "hk_forex_ratio.csv")
        hk_forex_df = pd.read_csv(forex_ratio_path, index_col=0)
        logger.info(f"Loaded forex ratio data: {len(hk_forex_df)} rows")
        
        # 3. 读取股票数据
        stock_dict = {}
        a_dt_size_dict = {}
        hk_dt_size_dict = {}
        
        for line in tqdm(ah_df.to_dict(orient="records"), desc="Loading stock data"):
            hk_code = line["hk_code"]
            ts_code = line["ts_code"]
            name = line["name"]
            
            try:
                # 读取A股数据
                a_path = os.path.join(self.input_dir, f"daily_{ts_code}.csv")
                a_org_stock_df = pd.read_csv(a_path)
                
                # 读取HK股数据
                hk_path = os.path.join(self.input_dir, f"hk_daily_{hk_code}.csv")
                hk_org_stock_df = pd.read_csv(hk_path)
                
                # 获取日期列表
                hk_dt_list = sorted(hk_org_stock_df.loc[:, "trade_date"].unique().tolist())
                min_hk_dt = min(hk_dt_list)
                a_dt_list = sorted(a_org_stock_df.loc[:, "trade_date"].unique().tolist())
                a_dt_list = [x for x in a_dt_list if x >= min_hk_dt]
                
                stock_dict[name] = {
                    "a_code": ts_code,
                    "hk_code": hk_code,
                    "a_org_stock_df": a_org_stock_df,
                    "hk_org_stock_df": hk_org_stock_df,
                    "hk_dt_list": hk_dt_list,
                    "a_dt_list": a_dt_list,
                }
                
                # 统计日期覆盖
                for dt in a_dt_list:
                    a_dt_size_dict[dt] = a_dt_size_dict.get(dt, 0) + 1
                
                for dt in hk_dt_list:
                    hk_dt_size_dict[dt] = hk_dt_size_dict.get(dt, 0) + 1
                
            except Exception as e:
                logger.warning(f"Failed to load {name} ({ts_code}/{hk_code}): {e}")
                continue
        
        logger.info(f"Loaded {len(stock_dict)} stock pairs")
        
        # 存入context
        self.context.ah_df = ah_df
        self.context.hk_forex_df = hk_forex_df
        self.context.stock_dict = stock_dict
        self.context.dt_a_list = sorted(a_dt_size_dict.keys())
        self.context.dt_hk_list = sorted(hk_dt_size_dict.keys())

    def _prepare_weekly_dates(self):
        """准备周频日期列表"""
        dt_a_weekly_list = []
        monday_friday_list: List[List[str]] = get_monday_fridays(
            self.context.dt_a_list[0],
            self.context.dt_a_list[-1]
        )
        for monday_friday in monday_friday_list:
            monday = str(monday_friday[0])
            friday = str(monday_friday[1])
            dt_a_weekly = [x for x in self.context.dt_a_list if monday <= str(x) <= friday]
            if dt_a_weekly:
                dt_a_weekly_list.append(dt_a_weekly[-1])
        
        logger.info(f"Generated {len(dt_a_weekly_list)} weekly dates")
        self.context.dt_a_weekly_list = dt_a_weekly_list

    def execute(self):
        """执行特征生成"""
        self._ensure_output_dir()
        
        # 从文件加载数据（支持独立运行和Pipeline运行）
        self._load_data_from_files()
        
        # 设置参数到context
        self.context.use_open = self.use_open
        self.context.use_weekly = self.use_weekly
        
        # 选择日频或周频
        if self.use_weekly:
            # 准备周频日期
            self._prepare_weekly_dates()
            f_op = self.ops[1]  # AhWeeklyFeatureOp
            dt_list = self.context.dt_a_weekly_list
            cache_name = "feature_weekly.csv"
        else:
            f_op = self.ops[0]  # AhDailyFeatureOp
            dt_list = self.context.dt_a_list
            cache_name = "feature_daily.csv"
        
        logger.info(f"Generating features for {len(dt_list)} dates using {'weekly' if self.use_weekly else 'daily'} mode")
        
        # 并行执行特征生成
        result = self.submit_and_join_parallel_op(op=f_op, dt=dt_list)
        
        # 合并结果
        df = pd.DataFrame(result).sort_values(["dt", "code"])
        
        # 验证数据
        nan_size = df.isnull().sum().sum()
        if nan_size > 0:
            logger.warning(f"Feature table has {nan_size} NaN values")
        
        # 保存
        output_path = os.path.join(self.output_dir, cache_name)
        df.to_csv(output_path, index=False)
        logger.info(f"Saved feature table to {output_path}, shape={df.shape}")
        
        return {
            "feature_count": len(df),
            "date_count": len(dt_list),
            "output_path": output_path
        }


class AhDailyFeatureOp(BaseOp):
    """生成日频特征（子Op）"""

    def execute(self):
        result = []
        dt = self.context.dt
        use_open: bool = self.context.use_open
        hk_forex_df = self.context.hk_forex_df
        
        # 获取汇率（晚一天）
        hk_forex_dt_list = [x for x in sorted(hk_forex_df.index.unique()) if x < dt]
        if not hk_forex_dt_list:
            logger.warning(f"No forex data available for dt={dt}")
            return result
        
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

            # 检查数据是否充足
            if dt_a_index is None or len(a_dt_list[:dt_a_index + 1]) < 2:
                continue

            if dt_hk_index is None or len(hk_dt_list[:dt_hk_index + 1]) < 2:
                continue

            # 当前价格和成交额
            current_a_close = a_org_stock_df.loc[a_dt_list[dt_a_index], "close"]
            current_hk_close = hk_org_stock_df.loc[hk_dt_list[dt_hk_index], "close"]

            current_a_amount = a_org_stock_df.loc[a_dt_list[dt_a_index], "amount"]
            current_hk_amount = hk_org_stock_df.loc[hk_dt_list[dt_hk_index], "amount"]

            current_a_uplift = a_org_stock_df.loc[a_dt_list[dt_a_index], "pct_chg"]
            current_hk_uplift = hk_org_stock_df.loc[hk_dt_list[dt_hk_index], "pct_chg"]

            # 计算标签（未来收益）
            if use_open:
                # 使用开盘价计算未来收益，避免回测look-ahead bias
                if dt_a_index < len(a_dt_list) - 2:
                    t1_open_close_ratio = a_org_stock_df.loc[a_dt_list[dt_a_index + 1], "close"] / \
                                         a_org_stock_df.loc[a_dt_list[dt_a_index + 1], "open"]
                    t2_open_close_ratio = a_org_stock_df.loc[a_dt_list[dt_a_index + 2], "close"] / \
                                         a_org_stock_df.loc[a_dt_list[dt_a_index + 2], "open"]
                    next_a_uplift = a_org_stock_df.loc[a_dt_list[dt_a_index + 2], "pct_chg"]
                    next_a_uplift = ((1 + next_a_uplift / 100) / t2_open_close_ratio * t1_open_close_ratio - 1) * 100
                else:
                    next_a_uplift = 0

                if dt_hk_index < len(hk_dt_list) - 2:
                    t1_open_close_ratio = hk_org_stock_df.loc[hk_dt_list[dt_hk_index + 1], "close"] / \
                                          hk_org_stock_df.loc[hk_dt_list[dt_hk_index + 1], "open"]
                    t2_open_close_ratio = hk_org_stock_df.loc[hk_dt_list[dt_hk_index + 2], "close"] / \
                                          hk_org_stock_df.loc[hk_dt_list[dt_hk_index + 2], "open"]
                    next_hk_uplift = hk_org_stock_df.loc[hk_dt_list[dt_hk_index + 2], "pct_chg"]
                    next_hk_uplift = ((1 + next_hk_uplift / 100) / t2_open_close_ratio * t1_open_close_ratio - 1) * 100
                else:
                    next_hk_uplift = 0

            else:
                # 直接使用下一天的收益
                if dt_a_index < len(a_dt_list) - 1:
                    next_a_uplift = a_org_stock_df.loc[a_dt_list[dt_a_index + 1], "pct_chg"]
                else:
                    next_a_uplift = 0

                if dt_hk_index < len(hk_dt_list) - 1:
                    next_hk_uplift = hk_org_stock_df.loc[hk_dt_list[dt_hk_index + 1], "pct_chg"]
                else:
                    next_hk_uplift = 0

            # 基础特征
            t_result["current_hk_close"] = current_hk_close
            t_result["current_a_close"] = current_a_close
            t_result["hk_forex_ratio"] = hk_forex_ratio

            t_result["a_flag"] = 1 if dt in a_dt_list else 0
            t_result["hk_flag"] = 1 if dt in hk_dt_list else 0

            t_result["a_uplift"] = current_a_uplift
            t_result["hk_uplift"] = current_hk_uplift

            # 历史平均涨跌幅特征
            for i in [1, 3, 5, 10, 20]:
                a_start_idx = max(0, dt_a_index - (i - 1))
                hk_start_idx = max(0, dt_hk_index - (i - 1))

                a_date_slice = a_dt_list[a_start_idx: dt_a_index + 1]
                hk_date_slice = hk_dt_list[hk_start_idx: dt_hk_index + 1]

                a_matched = a_org_stock_df.loc[a_org_stock_df.index.isin(a_date_slice), "pct_chg"]
                hk_matched = hk_org_stock_df.loc[hk_org_stock_df.index.isin(hk_date_slice), "pct_chg"]

                t_result[f"avg_{i}d_a_pct"] = a_matched.mean() if len(a_matched) > 0 else 0
                t_result[f"avg_{i}d_hk_pct"] = hk_matched.mean() if len(hk_matched) > 0 else 0

            # AH比价和成交额比
            t_result["ah_amount"] = (current_hk_amount / current_a_amount - 1) if current_a_amount != 0 else 0
            t_result["ah_ratio"] = current_hk_close * hk_forex_ratio / current_a_close

            # 标签
            t_result["a_label"] = next_a_uplift
            t_result["hk_label"] = next_hk_uplift

            result.append(t_result)

        return result


class AhWeeklyFeatureOp(BaseOp):
    """生成周频特征（子Op）"""

    def execute(self):
        result = []
        dt = self.context.dt
        use_open: bool = self.context.use_open
        hk_forex_df = self.context.hk_forex_df
        
        # 获取汇率（晚一天）
        hk_forex_dt_list = [x for x in sorted(hk_forex_df.index.unique()) if x < dt]
        if not hk_forex_dt_list:
            logger.warning(f"No forex data available for dt={dt}")
            return result
        
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

            # 计算下周的日期范围（用于标签）
            dt_a_index: int = a_dt_list.index(dt)
            if dt_a_index != len(a_dt_list) - 1:
                start_dt = a_dt_list[dt_a_index + 1]
            else:
                start_dt = dt

            end_dt = next_friday_or_same(str(start_dt))
            label_dts = [x for x in a_dt_list if int(start_dt) <= x <= int(end_dt)]
            
            if not label_dts:
                continue
                
            end_dt = label_dts[-1]
            
            if start_dt > end_dt:
                logger.warning(f"{name} dt={dt} start_dt={start_dt} > end_dt={end_dt}")
                continue

            hk_dt_list = stock_info["hk_dt_list"]
            dt_hk_index = find_dt_less_index(dt, hk_dt_list)

            # 检查数据是否充足
            if dt_a_index is None or len(a_dt_list[:dt_a_index + 1]) < 2:
                continue

            if dt_hk_index is None or len(hk_dt_list[:dt_hk_index + 1]) < 2:
                continue

            # 当前价格和成交额
            current_a_close = a_org_stock_df.loc[a_dt_list[dt_a_index], "close"]
            current_hk_close = hk_org_stock_df.loc[hk_dt_list[dt_hk_index], "close"]

            current_a_amount = a_org_stock_df.loc[a_dt_list[dt_a_index], "amount"]
            current_hk_amount = hk_org_stock_df.loc[hk_dt_list[dt_hk_index], "amount"]

            # 5日平均成交额
            current5_a_amount = a_org_stock_df.loc[a_dt_list[max(dt_a_index - 4, 0):dt_a_index + 1], "amount"].mean()
            current5_hk_amount = hk_org_stock_df.loc[hk_dt_list[max(dt_hk_index - 4, 0):dt_hk_index + 1], "amount"].mean()

            current_a_uplift = a_org_stock_df.loc[a_dt_list[dt_a_index], "pct_chg"]
            current_hk_uplift = hk_org_stock_df.loc[hk_dt_list[dt_hk_index], "pct_chg"]

            # 计算周收益（第一天用开盘价，后续天累计收盘价）
            if not use_open:
                logger.error("Weekly feature must use open price mode")
                raise ValueError("use_open must be True for weekly features")
            
            next_a_uplift = a_org_stock_df.loc[int(label_dts[0]), "close"] / \
                           a_org_stock_df.loc[int(label_dts[0]), "open"]
            for x_dt in label_dts[1:]:
                next_a_uplift *= (1 + a_org_stock_df.loc[int(x_dt), "pct_chg"] / 100)
            next_a_uplift = (next_a_uplift - 1) * 100

            next_hk_uplift = 0  # 周频不计算HK的周收益

            # 基础特征
            t_result["current_hk_close"] = current_hk_close
            t_result["current_a_close"] = current_a_close
            t_result["hk_forex_ratio"] = hk_forex_ratio

            t_result["a_flag"] = 1 if dt in a_dt_list else 0
            t_result["hk_flag"] = 1 if dt in hk_dt_list else 0

            t_result["a_uplift"] = current_a_uplift
            t_result["hk_uplift"] = current_hk_uplift

            # 历史平均涨跌幅特征
            for i in [1, 3, 5, 10, 20]:
                a_start_idx = max(0, dt_a_index - (i - 1))
                hk_start_idx = max(0, dt_hk_index - (i - 1))

                a_date_slice = a_dt_list[a_start_idx: dt_a_index + 1]
                hk_date_slice = hk_dt_list[hk_start_idx: dt_hk_index + 1]

                a_matched = a_org_stock_df.loc[a_org_stock_df.index.isin(a_date_slice), "pct_chg"]
                hk_matched = hk_org_stock_df.loc[hk_org_stock_df.index.isin(hk_date_slice), "pct_chg"]

                t_result[f"avg_{i}d_a_pct"] = a_matched.mean() if len(a_matched) > 0 else 0
                t_result[f"avg_{i}d_hk_pct"] = hk_matched.mean() if len(hk_matched) > 0 else 0

            # AH比价和成交额比
            t_result["ah_amount"] = (current_hk_amount / current_a_amount - 1) if current_a_amount != 0 else 0
            t_result["ah_amount5"] = (current5_hk_amount / current5_a_amount - 1) if current5_a_amount != 0 else 0
            t_result["ah_ratio"] = current_hk_close * hk_forex_ratio / current_a_close

            # 标签
            t_result["a_label"] = next_a_uplift
            t_result["hk_label"] = next_hk_uplift

            result.append(t_result)

        return result

