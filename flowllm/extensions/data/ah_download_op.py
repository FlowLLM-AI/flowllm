"""AH Stock Data Download Operation"""

import os
from typing import Dict

import pandas as pd
from loguru import logger
from tqdm import tqdm

from ...core.context import C
from ...core.op import BaseOp
from ...core.utils import TushareClient


@C.register_op()
class AhDownloadOp(BaseOp):
    """Download AH stock data from Tushare API."""

    def __init__(self, output_dir: str = "data/origin", **kwargs):
        super().__init__(**kwargs)
        self.output_dir = output_dir
        self.ts_client = TushareClient()

    def _ensure_output_dir(self) -> None:
        """Create output directory if not exists."""
        os.makedirs(self.output_dir, exist_ok=True)

    def _save_dataframe(self, df: pd.DataFrame, filename: str) -> None:
        """Save DataFrame to CSV file."""
        output_path = os.path.join(self.output_dir, filename)
        df.to_csv(output_path, index=False)
        logger.info(f"Saved {filename}: {len(df)} rows")

    def _download_ah_comparison(self) -> pd.DataFrame:
        """Download AH comparison data and return latest pairs."""
        logger.info("Downloading AH comparison data...")
        df = self.ts_client.request(api_name="stk_ah_comparison")
        self._save_dataframe(df, "stk_ah_comparison.csv")
        ah_df = df.loc[df.trade_date == df.trade_date.max(), ["hk_code", "ts_code", "name"]].copy()
        logger.info(f"Found {len(ah_df)} AH pairs")
        return ah_df

    def _download_forex_data(self) -> Dict[str, pd.DataFrame]:
        """Download forex rates for USD/CNH and USD/HKD."""
        logger.info("Downloading forex data...")
        forex_dict = {}
        for code in ["USDCNH.FXCM", "USDHKD.FXCM"]:
            df = self.ts_client.request(api_name="fx_daily", ts_code=code)
            self._save_dataframe(df, f"fx_daily_{code}.csv")
            forex_dict[code] = df
        return forex_dict

    def _download_stock_data(self, ah_df: pd.DataFrame) -> int:
        """Download daily stock data for A-shares and H-shares."""
        logger.info("Downloading stock daily data...")
        success_count = 0

        for record in tqdm(ah_df.to_dict(orient="records"), desc="Downloading stocks"):
            hk_code, ts_code, name = record["hk_code"], record["ts_code"], record["name"]

            a_df = self.ts_client.request(api_name="daily", ts_code=ts_code)
            if a_df.empty:
                logger.warning(f"Empty A-share data for {name} ({ts_code})")
                continue
            self._save_dataframe(a_df, f"daily_{ts_code}.csv")

            a_basic_df = self.ts_client.request(api_name="daily_basic", ts_code=ts_code)
            if a_basic_df.empty:
                logger.warning(f"Empty A-share basic data for {name} ({ts_code})")
                continue
            self._save_dataframe(a_basic_df, f"daily_basic_{ts_code}.csv")

            hk_df = self.ts_client.request(api_name="hk_daily", ts_code=hk_code)
            if hk_df.empty:
                logger.warning(f"Empty HK data for {name} ({hk_code})")
                continue
            self._save_dataframe(hk_df, f"hk_daily_{hk_code}.csv")

            success_count += 1

        logger.info(f"Successfully downloaded {success_count}/{len(ah_df)} stock pairs")
        return success_count

    def execute(self) -> None:
        """Execute download process."""
        self._ensure_output_dir()
        ah_df = self._download_ah_comparison()
        forex_dict = self._download_forex_data()
        stock_count = self._download_stock_data(ah_df)
        logger.info(
            f"Download completed - AH pairs: {len(ah_df)}, " f"Forex: {len(forex_dict)}, Stocks: {stock_count}",
        )
        logger.info(f"All data saved to {self.output_dir}")
