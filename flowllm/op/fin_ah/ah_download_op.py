"""
AH股数据下载Op
负责从Tushare下载原始数据：
1. A股日频数据
2. HK股日频数据
3. AH对比数据
4. 汇率数据（USDCNH, USDHKD）
"""
import os
from typing import Dict

import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.app import FlowLLMApp
from flowllm.context.service_context import C
from flowllm.op import BaseOp
from flowllm.utils.tushare_client import TushareClient

FOREX_CODES = ['USDCNH.FXCM', 'USDHKD.FXCM']


@C.register_op(register_app="FlowLLM")
class AhDownloadOp(BaseOp):
    """下载AH股原始数据"""

    def __init__(self, output_dir: str = "data/origin", **kwargs):
        super().__init__(**kwargs)
        self.output_dir = output_dir
        self.ts_client = TushareClient()

    def _ensure_output_dir(self) -> None:
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)

    def _save_dataframe(self, df: pd.DataFrame, filename: str) -> None:
        """保存DataFrame到CSV"""
        output_path = os.path.join(self.output_dir, filename)
        df.to_csv(output_path, index=False)
        logger.info(f"Saved {filename}: {len(df)} rows")

    def _download_ah_comparison(self) -> pd.DataFrame:
        """下载AH对比数据"""
        logger.info("Downloading AH comparison data...")
        df = self.ts_client.request(api_name="stk_ah_comparison")
        
        # 保存完整数据
        self._save_dataframe(df, "stk_ah_comparison.csv")
        
        # 返回最新的AH对比关系
        ah_df = df.loc[df.trade_date == df.trade_date.max(), ["hk_code", "ts_code", "name"]].copy()
        logger.info(f"Found {len(ah_df)} AH pairs")
        return ah_df

    def _download_forex_data(self) -> Dict[str, pd.DataFrame]:
        """下载汇率数据"""
        logger.info("Downloading forex data...")
        forex_dict = {}
        
        for code in FOREX_CODES:
            df = self.ts_client.request(api_name="fx_daily", ts_code=code)
            self._save_dataframe(df, f"fx_daily_{code}.csv")
            forex_dict[code] = df
        
        return forex_dict

    def _download_stock_data(self, ah_df: pd.DataFrame) -> int:
        """下载A股和HK股日频数据，返回成功下载的股票对数量"""
        logger.info("Downloading stock daily data...")
        success_count = 0
        
        for record in tqdm(ah_df.to_dict(orient="records"), desc="Downloading stocks"):
            hk_code, ts_code, name = record["hk_code"], record["ts_code"], record["name"]
            
            # 下载A股数据
            a_df = self.ts_client.request(api_name="daily", ts_code=ts_code)
            if a_df.empty:
                logger.warning(f"Empty A-share data for {name} ({ts_code})")
                continue
            self._save_dataframe(a_df, f"daily_{ts_code}.csv")

            # 下载HK股数据
            hk_df = self.ts_client.request(api_name="hk_daily", ts_code=hk_code)
            if hk_df.empty:
                logger.warning(f"Empty HK data for {name} ({hk_code})")
                continue
            self._save_dataframe(hk_df, f"hk_daily_{hk_code}.csv")

            success_count += 1
        
        logger.info(f"Successfully downloaded {success_count}/{len(ah_df)} stock pairs")
        return success_count

    def execute(self) -> None:
        """执行下载"""
        self._ensure_output_dir()
        
        # 1. 下载AH对比数据
        ah_df = self._download_ah_comparison()
        
        # 2. 下载汇率数据
        forex_dict = self._download_forex_data()
        
        # 3. 下载股票数据
        stock_count = self._download_stock_data(ah_df)
        
        logger.info(
            f"Download completed - AH pairs: {len(ah_df)}, "
            f"Forex: {len(forex_dict)}, Stocks: {stock_count}"
        )
        logger.info(f"All data saved to {self.output_dir}")


def main():
    """下载AH股数据"""
    with FlowLLMApp(load_default_config=True) as app:
        op = AhDownloadOp(output_dir="data/origin")
        op.call()


if __name__ == "__main__":
    main()
