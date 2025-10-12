"""
AH股数据修复Op
负责修复原始数据中的问题：
1. 处理NaN/null值
2. 修复价格为0的情况
3. 修复pre_close缺失导致的change和pct_chg错误
"""
import os
import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.context.service_context import C
from flowllm.op import BaseOp


@C.register_op(register_app="FlowLLM")
class AhFixOp(BaseOp):
    """修复AH股原始数据"""

    def __init__(self,
                 input_dir: str = "data/origin",
                 output_dir: str = "data/fixed",
                 min_date: int = 20160101,
                 **kwargs):
        super().__init__(**kwargs)
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.min_date = min_date

    def _ensure_output_dir(self):
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def fix_hk_df(df: pd.DataFrame) -> pd.DataFrame:
        """
        修复HK股数据的pre_close问题
        HK数据经常出现pre_close为NaN或0的情况，需要用前一天的close填充
        """
        # 先排序，确保时间顺序正确
        df = df.sort_values("trade_date", ascending=False).copy()
        
        # 先计算前一天(时间降序，所以是shift(-1))的close值
        prev_close = df["close"].shift(-1)
        
        # 找出pre_close有问题的行
        flag_index = (df["pre_close"].isna()) | (df["pre_close"] == 0.0)
        
        # 使用 where 条件赋值：如果 flag_index 为 True，则用 prev_close，否则保持原值
        df["pre_close"] = df["pre_close"].where(~flag_index, prev_close)
        
        # 重新计算change和pct_chg（使用更新后的pre_close值）
        df.loc[flag_index, "change"] = df.loc[flag_index, "close"] - df.loc[flag_index, "pre_close"]
        df.loc[flag_index, "pct_chg"] = (df.loc[flag_index, "close"] / df.loc[flag_index, "pre_close"] - 1) * 100
        
        # 去掉最后一行（因为它没有pre_close参考）
        df = df[:-1].copy()
        
        return df

    @staticmethod
    def validate_df(df: pd.DataFrame, name: str) -> bool:
        """
        验证数据是否有问题
        返回True表示数据有效，False表示数据无效
        """
        # 检查是否有NaN
        nan_size = df.isnull().sum().sum()
        if nan_size > 0:
            logger.warning(f"{name} has {nan_size} NaN values")
            return False
        
        # 检查关键列是否有0值
        for col in ["close", "open", "high", "low"]:
            if col in df.columns:
                zero_count = (df[col] == 0).sum()
                if zero_count > 0:
                    logger.warning(f"{name} has {zero_count} zero values in {col}")
                    return False
        
        return True

    def _fix_forex_data(self) -> dict:
        """修复汇率数据"""
        logger.info("Fixing forex data...")
        forex_dict = {}
        
        for code in ['USDCNH.FXCM', 'USDHKD.FXCM']:
            input_path = os.path.join(self.input_dir, f"fx_daily_{code}.csv")
            df = pd.read_csv(input_path)
            
            # 过滤日期
            df = df.loc[df.trade_date > self.min_date].copy()
            
            # 前向填充NaN
            df = df.sort_values("trade_date").ffill()
            
            # 验证数据
            is_valid = self.validate_df(df, f"fx_{code}")
            
            if is_valid:
                output_path = os.path.join(self.output_dir, f"fx_daily_{code}.csv")
                df.to_csv(output_path, index=False)
                logger.info(f"Fixed and saved forex data to {output_path}")
                forex_dict[code] = df
            else:
                logger.error(f"Failed to fix forex data for {code}")
        
        return forex_dict

    def _process_forex_ratio(self, forex_dict: dict) -> pd.DataFrame:
        """处理汇率比率（CNH/HKD）"""
        logger.info("Processing forex ratio...")
        
        df_cnh = forex_dict['USDCNH.FXCM']
        df_hkd = forex_dict['USDHKD.FXCM']
        
        # 选择需要的列
        df_cnh = df_cnh.loc[:, ["trade_date", "bid_close"]].set_index("trade_date").rename(
            columns={"bid_close": "cnh_close"})
        df_hkd = df_hkd.loc[:, ["trade_date", "bid_close"]].set_index("trade_date").rename(
            columns={"bid_close": "hkd_close"})
        
        # 合并（使用outer join包含所有日期）
        hk_forex_df = df_cnh.join(df_hkd, how='outer').sort_index()
        
        # ⚠️ 只用前向填充！不能用后向填充，避免未来数据泄露（look-ahead bias）
        # 前向填充：用历史数据填充当前缺失值
        hk_forex_df = hk_forex_df.ffill()
        
        # 删除开头仍然有NaN的行（因为没有历史数据可填充）
        initial_nans = hk_forex_df.isnull().sum().sum()
        if initial_nans > 0:
            logger.warning(f"Dropping {initial_nans} NaN values at the beginning (no historical data)")
            hk_forex_df = hk_forex_df.dropna()
        
        # 验证：此时不应该还有NaN（除非数据本身有问题）
        remaining_nans = hk_forex_df.isnull().sum().sum()
        if remaining_nans > 0:
            logger.error(f"Still have {remaining_nans} NaN values after forward fill")
            logger.error(f"Rows with NaN:\n{hk_forex_df[hk_forex_df.isnull().any(axis=1)]}")
            raise ValueError(f"Forex data has {remaining_nans} NaN values after forward fill only")
        
        # 计算比率
        hk_forex_df.loc[:, "close"] = hk_forex_df.loc[:, "cnh_close"] / hk_forex_df.loc[:, "hkd_close"]
        
        # 最终验证
        nan_size = hk_forex_df.isnull().sum().sum()
        if nan_size > 0:
            logger.error(f"hk_forex_df has {nan_size} NaN values in calculated close")
            raise ValueError("Forex ratio has NaN values in close column")
        
        # 保存
        output_path = os.path.join(self.output_dir, "hk_forex_ratio.csv")
        hk_forex_df.to_csv(output_path)
        logger.info(f"Saved forex ratio to {output_path}, shape={hk_forex_df.shape}")
        logger.info(f"Date range: {hk_forex_df.index.min()} to {hk_forex_df.index.max()}")
        
        return hk_forex_df

    def _fix_stock_data(self, ah_df: pd.DataFrame) -> dict:
        """修复股票数据"""
        logger.info("Fixing stock data...")
        stock_dict = {}
        a_dt_size_dict = {}
        hk_dt_size_dict = {}
        
        for line in tqdm(ah_df.to_dict(orient="records"), desc="Fixing stocks"):
            hk_code = line["hk_code"]
            ts_code = line["ts_code"]
            name = line["name"]
            
            try:
                # 读取A股数据
                a_input_path = os.path.join(self.input_dir, f"daily_{ts_code}.csv")
                a_org_stock_df = pd.read_csv(a_input_path)
                a_org_stock_df = a_org_stock_df.loc[a_org_stock_df.trade_date > self.min_date].copy()
                
                # 读取HK股数据
                hk_input_path = os.path.join(self.input_dir, f"hk_daily_{hk_code}.csv")
                hk_org_stock_df = pd.read_csv(hk_input_path)
                hk_org_stock_df = hk_org_stock_df.loc[hk_org_stock_df.trade_date > self.min_date].copy()
                
                # 修复HK数据
                hk_org_stock_df = self.fix_hk_df(hk_org_stock_df)
                
                # 验证数据
                if not self.validate_df(a_org_stock_df, f"{name}.{ts_code}.A"):
                    logger.warning(f"Skipping {name} due to invalid A-share data")
                    continue
                
                if not self.validate_df(hk_org_stock_df, f"{name}.{hk_code}.HK"):
                    logger.warning(f"Skipping {name} due to invalid HK data")
                    continue
                
                # 获取日期列表
                hk_dt_list = sorted(hk_org_stock_df.loc[:, "trade_date"].unique().tolist())
                min_hk_dt = min(hk_dt_list)
                a_dt_list = sorted(a_org_stock_df.loc[:, "trade_date"].unique().tolist())
                a_dt_list = [x for x in a_dt_list if x >= min_hk_dt]
                
                # 保存修复后的数据
                a_output_path = os.path.join(self.output_dir, f"daily_{ts_code}.csv")
                a_org_stock_df.to_csv(a_output_path, index=False)
                
                hk_output_path = os.path.join(self.output_dir, f"hk_daily_{hk_code}.csv")
                hk_org_stock_df.to_csv(hk_output_path, index=False)
                
                # 存储到字典
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
                logger.error(f"Failed to fix {name} ({ts_code}/{hk_code}): {e}")
                continue
        
        logger.info(f"Fixed {len(stock_dict)} stock pairs")
        logger.info(f"A-share date range: {min(a_dt_size_dict.keys())} to {max(a_dt_size_dict.keys())}, "
                   f"total {len(a_dt_size_dict)} trading days")
        logger.info(f"HK date range: {min(hk_dt_size_dict.keys())} to {max(hk_dt_size_dict.keys())}, "
                   f"total {len(hk_dt_size_dict)} trading days")
        
        return stock_dict, a_dt_size_dict, hk_dt_size_dict

    def execute(self):
        """执行修复"""
        self._ensure_output_dir()
        
        # 读取AH对比数据
        ah_df_path = os.path.join(self.input_dir, "stk_ah_comparison.csv")
        df = pd.read_csv(ah_df_path)
        ah_df = df.loc[df.trade_date == df.trade_date.max(), ["hk_code", "ts_code", "name"]]
        logger.info(f"Loaded {len(ah_df)} AH pairs")
        
        # 1. 修复汇率数据
        forex_dict = self._fix_forex_data()
        
        # 2. 处理汇率比率
        hk_forex_df = self._process_forex_ratio(forex_dict)
        
        # 3. 修复股票数据
        stock_dict, a_dt_size_dict, hk_dt_size_dict = self._fix_stock_data(ah_df)
        
        result = {
            "stock_pairs": len(stock_dict),
            "a_trading_days": len(a_dt_size_dict),
            "hk_trading_days": len(hk_dt_size_dict),
            "output_dir": self.output_dir
        }
        
        logger.info(f"Fix completed: {result}")
        return result

