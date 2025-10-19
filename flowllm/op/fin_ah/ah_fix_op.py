"""
AH股数据修复Op
负责修复原始数据中的问题：
1. 处理NaN/null值
2. 修复价格为0的情况
3. 修复pre_close缺失导致的change和pct_chg错误
"""
import os
from typing import Dict, Tuple

import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.app import FlowLLMApp
from flowllm.context.service_context import C
from flowllm.op import BaseOp

FOREX_CODES = ['USDCNH.FXCM', 'USDHKD.FXCM']
PRICE_COLUMNS = ["close", "open", "high", "low", "pre_close", "vol", "amount"]


@C.register_op(register_app="FlowLLM")
class AhFixOp(BaseOp):
    """修复AH股原始数据"""

    def __init__(
        self,
        input_dir: str = "data/origin",
        output_dir: str = "data/fixed",
        min_date: int = 20160101,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.min_date = min_date

    def _ensure_output_dir(self) -> None:
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def fix_hk_df(df: pd.DataFrame) -> pd.DataFrame:
        """
        修复HK股数据的pre_close问题
        HK数据经常出现pre_close为NaN或0的情况，需要用前一天的close填充
        """
        # 按时间降序排序
        df = df.sort_values("trade_date", ascending=False).copy()
        
        # 计算前一天的close值（时间降序，所以是shift(-1)）
        df.loc[:, "prev_close"] = df["close"].shift(-1)
        
        # 找出pre_close有问题的行
        need_fix = (df["pre_close"].isna()) | (df["pre_close"] == 0.0)
        
        # 修复pre_close
        df.loc[need_fix, "pre_close"] = df.loc[need_fix, "prev_close"]
        
        # 重新计算change和pct_chg
        df.loc[need_fix, "change"] = df.loc[need_fix, "close"] - df.loc[need_fix, "pre_close"]
        df.loc[need_fix, "pct_chg"] = (df.loc[need_fix, "close"] / df.loc[need_fix, "pre_close"] - 1) * 100

        # 去掉最后一行（没有前一天的close作为参考）
        return df.iloc[:-1].copy()

    @staticmethod
    def validate_df(df: pd.DataFrame, name: str) -> bool:
        """验证数据是否有效（无NaN，无0价格）"""
        # 检查NaN
        nan_count = df.isnull().sum().sum()
        if nan_count > 0:
            logger.warning(f"{name}: {nan_count} NaN values")
            return False
        
        # 检查关键列的0值
        for col in PRICE_COLUMNS:
            if col in df.columns:
                zero_count = (df[col] == 0).sum()
                if zero_count > 0:
                    logger.warning(f"{name}: {zero_count} zero values in '{col}'")
                    return False
        
        return True

    def _save_dataframe(self, df: pd.DataFrame, filename: str) -> None:
        """保存DataFrame到CSV"""
        output_path = os.path.join(self.output_dir, filename)
        df.to_csv(output_path, index=False)

    def _fix_forex_data(self) -> Dict[str, pd.DataFrame]:
        """修复汇率数据"""
        logger.info("Fixing forex data...")
        forex_dict = {}
        
        for code in FOREX_CODES:
            input_path = os.path.join(self.input_dir, f"fx_daily_{code}.csv")
            df = pd.read_csv(input_path)
            
            # 过滤日期并前向填充（按时间升序排序后前向填充）
            df = df.loc[df.trade_date > self.min_date].copy()
            df = df.sort_values("trade_date", ascending=True).ffill()
            
            # 验证并保存
            if self.validate_df(df, f"fx_{code}"):
                self._save_dataframe(df, f"fx_daily_{code}.csv")
                forex_dict[code] = df
                logger.info(f"Fixed forex {code}: {len(df)} rows")
            else:
                raise ValueError(f"Failed to fix forex data for {code}")
        
        return forex_dict

    def _process_forex_ratio(self, forex_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """处理汇率比率（CNH/HKD），避免look-ahead bias"""
        logger.info("Processing forex ratio...")
        
        # 提取关键列
        df_cnh = forex_dict['USDCNH.FXCM'][["trade_date", "bid_close"]].set_index("trade_date")
        df_cnh.columns = ["cnh_close"]
        
        df_hkd = forex_dict['USDHKD.FXCM'][["trade_date", "bid_close"]].set_index("trade_date")
        df_hkd.columns = ["hkd_close"]
        
        # 合并并只用前向填充（避免未来数据泄露） outer填充
        hk_forex_df = df_cnh.join(df_hkd, how='outer').sort_index().ffill()
        
        # 删除开头的NaN（没有历史数据可填充）
        initial_nan_count = hk_forex_df.isnull().sum().sum()
        if initial_nan_count > 0:
            logger.warning(f"Dropping {initial_nan_count} leading NaN values (no historical data)")
            hk_forex_df = hk_forex_df.dropna()
        
        # 验证不应再有NaN
        if hk_forex_df.isnull().sum().sum() > 0:
            raise ValueError("Forex data still has NaN values after forward fill")
        
        # 计算CNH/HKD比率
        hk_forex_df["close"] = hk_forex_df["cnh_close"] / hk_forex_df["hkd_close"]
        
        # 最终验证
        if hk_forex_df["close"].isnull().sum() > 0:
            raise ValueError("Forex ratio has NaN values in close column")
        
        # 保存
        output_path = os.path.join(self.output_dir, "hk_forex_ratio.csv")
        hk_forex_df.to_csv(output_path)
        logger.info(
            f"Saved forex ratio: {len(hk_forex_df)} rows, "
            f"date range {hk_forex_df.index.min()}-{hk_forex_df.index.max()}"
        )
        
        return hk_forex_df

    def _fix_stock_data(self, ah_df: pd.DataFrame) -> Tuple[int, int, int]:
        """修复股票数据，返回(成功数量, A股交易日数量, HK交易日数量)"""
        logger.info("Fixing stock data...")
        success_count = 0
        a_date_counter = {}
        hk_date_counter = {}
        
        for record in tqdm(ah_df.to_dict(orient="records"), desc="Fixing stocks"):
            hk_code, ts_code, name = record["hk_code"], record["ts_code"], record["name"]

            # 读取A股数据，A股数据的成交额需要乘1K
            a_df = pd.read_csv(os.path.join(self.input_dir, f"daily_{ts_code}.csv"))
            a_df = a_df.loc[a_df.trade_date > self.min_date].copy()

            # 读取并修复HK股数据
            hk_df = pd.read_csv(os.path.join(self.input_dir, f"hk_daily_{hk_code}.csv"))
            hk_df = hk_df.loc[hk_df.trade_date > self.min_date].copy()
            hk_df = self.fix_hk_df(hk_df)

            # 验证数据有效性
            if not self.validate_df(a_df, f"{name}.A") or not self.validate_df(hk_df, f"{name}.HK"):
                raise RuntimeError(f"Skipping {name} due to invalid data")

            # 保存修复后的数据
            self._save_dataframe(a_df, f"daily_{ts_code}.csv")
            self._save_dataframe(hk_df, f"hk_daily_{hk_code}.csv")

            # 统计日期覆盖
            hk_dates = hk_df["trade_date"].unique()
            min_hk_date = hk_dates.min()
            a_dates = a_df.loc[a_df.trade_date >= min_hk_date, "trade_date"].unique()

            for dt in a_dates:
                a_date_counter[dt] = a_date_counter.get(dt, 0) + 1
            for dt in hk_dates:
                hk_date_counter[dt] = hk_date_counter.get(dt, 0) + 1

            success_count += 1
        
        # 输出统计信息
        logger.info(f"Fixed {success_count}/{len(ah_df)} stock pairs")
        if a_date_counter:
            logger.info(f"A-share: {len(a_date_counter)} trading days "
                        f"({min(a_date_counter.keys())} to {max(a_date_counter.keys())})")

        if hk_date_counter:
            logger.info(
                f"HK: {len(hk_date_counter)} trading days "
                f"({min(hk_date_counter.keys())} to {max(hk_date_counter.keys())})"
            )
        
        return success_count, len(a_date_counter), len(hk_date_counter)

    def execute(self) -> None:
        """执行修复"""
        self._ensure_output_dir()
        
        # 读取AH对比数据
        ah_df_path = os.path.join(self.input_dir, "stk_ah_comparison.csv")
        df = pd.read_csv(ah_df_path)
        ah_df = df.loc[df.trade_date == df.trade_date.max(), ["hk_code", "ts_code", "name"]].copy()
        logger.info(f"Loaded {len(ah_df)} AH pairs")
        
        # 1. 修复汇率数据
        forex_dict = self._fix_forex_data()
        
        # 2. 处理汇率比率
        self._process_forex_ratio(forex_dict)
        
        # 3. 修复股票数据
        stock_count, a_days, hk_days = self._fix_stock_data(ah_df)
        
        logger.info(
            f"Fix completed - Stocks: {stock_count}, "
            f"A days: {a_days}, HK days: {hk_days}"
        )
        logger.info(f"All fixed data saved to {self.output_dir}")


def main():
    """修复AH股数据"""
    with FlowLLMApp(load_default_config=True) as app:
        op = AhFixOp(input_dir="data/origin", output_dir="data/fixed")
        op.call()


if __name__ == "__main__":
    main()
