"""
AH stock data fix operation.
Fixes issues in raw data:
1. Handles NaN/null values
2. Fixes zero prices
3. Fixes change and pct_chg errors caused by missing pre_close
"""

import os
from typing import Dict, Tuple

import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.core.context import C
from flowllm.core.op import BaseOp


@C.register_op()
class AhFixOp(BaseOp):
    """Fix AH stock raw data"""

    def __init__(
        self,
        input_dir: str = "data/origin",
        output_dir: str = "data/fixed",
        min_date: int = 20160101,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.min_date = min_date

    def _ensure_output_dir(self) -> None:
        """Ensure output directory exists"""
        os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def fix_hk_df(df: pd.DataFrame) -> pd.DataFrame:
        """
        Fix pre_close issues in HK stock data.
        HK data often has NaN or 0 pre_close, fill with previous day's close.
        """
        # Sort by date descending
        df: pd.DataFrame = df.sort_values(by="trade_date", ascending=False)

        # Calculate previous day's close (shift(-1) for descending order)
        df.loc[:, "prev_close"] = df["close"].shift(-1)

        # Find rows with invalid pre_close
        need_fix = (df["pre_close"].isna()) | (df["pre_close"] == 0.0)

        # Fix pre_close
        df.loc[need_fix, "pre_close"] = df.loc[need_fix, "prev_close"]

        # Recalculate change and pct_chg
        df.loc[need_fix, "change"] = df.loc[need_fix, "close"] - df.loc[need_fix, "pre_close"]
        df.loc[need_fix, "pct_chg"] = (df.loc[need_fix, "close"] / df.loc[need_fix, "pre_close"] - 1) * 100

        # Remove last row (no previous day reference)
        return df.iloc[:-1].copy()

    @staticmethod
    def validate_df(df: pd.DataFrame, name: str) -> bool:
        """Validate data (no NaN, no zero prices)"""
        # Check NaN
        nan_count = df.isnull().sum().sum()
        if nan_count > 0:
            logger.warning(f"{name}: {nan_count} NaN values")
            return False

        # Check zero values in key columns
        for col in ["close", "open", "high", "low", "pre_close", "vol", "amount"]:
            if col in df.columns:
                zero_count = (df[col] == 0).sum()
                if zero_count > 0:
                    logger.warning(f"{name}: {zero_count} zero values in '{col}'")
                    return False

        return True

    @staticmethod
    def validate_basic_df(df: pd.DataFrame, name: str) -> bool:
        """Validate daily_basic data (check required fields only)"""
        # Check NaN in required fields
        required_cols = ["ts_code", "trade_date", "close"]
        for col in required_cols:
            if col not in df.columns:
                logger.warning(f"{name}: missing required column '{col}'")
                return False
            nan_count = df[col].isnull().sum()
            if nan_count > 0:
                logger.warning(f"{name}: {nan_count} NaN values in required column '{col}'")
                return False

        # Check zero values in close
        zero_count = (df["close"] == 0).sum()
        if zero_count > 0:
            logger.warning(f"{name}: {zero_count} zero values in 'close'")
            return False

        return True

    def _save_dataframe(self, df: pd.DataFrame, filename: str) -> None:
        """Save DataFrame to CSV"""
        output_path = os.path.join(self.output_dir, filename)
        df.to_csv(output_path, index=False)

    def _fix_forex_data(self) -> Dict[str, pd.DataFrame]:
        """Fix forex data"""
        logger.info("Fixing forex data...")
        forex_dict = {}

        for code in ["USDCNH.FXCM", "USDHKD.FXCM"]:
            input_path = os.path.join(self.input_dir, f"fx_daily_{code}.csv")
            df = pd.read_csv(input_path)

            # Filter by date and forward fill (sort ascending first)
            df = df.loc[df.trade_date > self.min_date].copy()
            df = df.sort_values("trade_date", ascending=True).ffill()

            # Validate and save
            if self.validate_df(df, f"fx_{code}"):
                self._save_dataframe(df, f"fx_daily_{code}.csv")
                forex_dict[code] = df
                logger.info(f"Fixed forex {code}: {len(df)} rows")
            else:
                raise ValueError(f"Failed to fix forex data for {code}")

        return forex_dict

    def _process_forex_ratio(self, forex_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Process forex ratio (CNH/HKD), avoid look-ahead bias"""
        logger.info("Processing forex ratio...")

        # Extract key columns
        df_cnh = forex_dict["USDCNH.FXCM"][["trade_date", "bid_close"]].set_index("trade_date")
        df_cnh.columns = ["cnh_close"]

        df_hkd = forex_dict["USDHKD.FXCM"][["trade_date", "bid_close"]].set_index("trade_date")
        df_hkd.columns = ["hkd_close"]

        # Merge and forward fill only (avoid future data leakage), outer join
        hk_forex_df = df_cnh.join(df_hkd, how="outer").sort_index().ffill()

        # Drop leading NaN (no historical data to fill)
        initial_nan_count = hk_forex_df.isnull().sum().sum()
        if initial_nan_count > 0:
            logger.warning(f"Dropping {initial_nan_count} leading NaN values (no historical data)")
            hk_forex_df = hk_forex_df.dropna()

        # Validate no NaN remains
        if hk_forex_df.isnull().sum().sum() > 0:
            raise ValueError("Forex data still has NaN values after forward fill")

        # Calculate CNH/HKD ratio
        hk_forex_df["close"] = hk_forex_df["cnh_close"] / hk_forex_df["hkd_close"]

        # Final validation
        if hk_forex_df["close"].isnull().sum() > 0:
            raise ValueError("Forex ratio has NaN values in close column")

        # Save
        output_path = os.path.join(self.output_dir, "hk_forex_ratio.csv")
        hk_forex_df.to_csv(output_path)
        logger.info(
            f"Saved forex ratio: {len(hk_forex_df)} rows, "
            f"date range {hk_forex_df.index.min()}-{hk_forex_df.index.max()}",
        )

        return hk_forex_df

    def _fix_stock_data(self, ah_df: pd.DataFrame) -> Tuple[int, int, int]:
        """Fix stock data, returns (success_count, A-share trading days, HK trading days)"""
        logger.info("Fixing stock data...")
        success_count = 0
        a_date_counter = {}
        hk_date_counter = {}

        for record in tqdm(ah_df.to_dict(orient="records"), desc="Fixing stocks"):
            hk_code, ts_code, name = record["hk_code"], record["ts_code"], record["name"]

            # Read A-share data (amount needs to be multiplied by 1K)
            a_df = pd.read_csv(os.path.join(self.input_dir, f"daily_{ts_code}.csv"))
            a_df = a_df.loc[a_df.trade_date > self.min_date].copy()

            # Read A-share daily_basic data
            a_basic_df = pd.read_csv(os.path.join(self.input_dir, f"daily_basic_{ts_code}.csv"))
            a_basic_df = a_basic_df.loc[a_basic_df.trade_date > self.min_date].copy()

            # Read and fix HK stock data
            hk_df = pd.read_csv(os.path.join(self.input_dir, f"hk_daily_{hk_code}.csv"))
            hk_df = hk_df.loc[hk_df.trade_date > self.min_date].copy()
            hk_df = self.fix_hk_df(hk_df)

            # Validate data
            if not self.validate_df(a_df, f"{name}.A") or not self.validate_df(hk_df, f"{name}.HK"):
                raise RuntimeError(f"Skipping {name} due to invalid data")

            # Validate daily_basic data
            if not self.validate_basic_df(a_basic_df, f"{name}.A.basic"):
                raise RuntimeError(f"Skipping {name} due to invalid daily_basic data")

            # Save fixed data
            self._save_dataframe(a_df, f"daily_{ts_code}.csv")
            self._save_dataframe(hk_df, f"hk_daily_{hk_code}.csv")
            self._save_dataframe(a_basic_df, f"daily_basic_{ts_code}.csv")

            # Count date coverage
            hk_dates = hk_df["trade_date"].unique()
            min_hk_date = hk_dates.min()
            a_dates = a_df.loc[a_df.trade_date >= min_hk_date, "trade_date"].unique()

            for dt in a_dates:
                a_date_counter[dt] = a_date_counter.get(dt, 0) + 1
            for dt in hk_dates:
                hk_date_counter[dt] = hk_date_counter.get(dt, 0) + 1

            success_count += 1

        # Output statistics
        logger.info(f"Fixed {success_count}/{len(ah_df)} stock pairs")
        if a_date_counter:
            logger.info(
                f"A-share: {len(a_date_counter)} trading days "
                f"({min(a_date_counter.keys())} to {max(a_date_counter.keys())})",
            )

        if hk_date_counter:
            logger.info(
                f"HK: {len(hk_date_counter)} trading days "
                f"({min(hk_date_counter.keys())} to {max(hk_date_counter.keys())})",
            )

        return success_count, len(a_date_counter), len(hk_date_counter)

    def execute(self):
        """Execute fix operation"""
        self._ensure_output_dir()

        # Read AH comparison data
        ah_df_path = os.path.join(self.input_dir, "stk_ah_comparison.csv")
        df = pd.read_csv(ah_df_path)
        ah_df = df.loc[df.trade_date == df.trade_date.max(), ["hk_code", "ts_code", "name"]].copy()
        logger.info(f"Loaded {len(ah_df)} AH pairs")

        # 1. Fix forex data
        forex_dict = self._fix_forex_data()

        # 2. Process forex ratio
        self._process_forex_ratio(forex_dict)

        # 3. Fix stock data
        stock_count, a_days, hk_days = self._fix_stock_data(ah_df)

        logger.info(
            f"Fix completed - Stocks: {stock_count}, A days: {a_days}, HK days: {hk_days}",
        )
        logger.info(f"All fixed data saved to {self.output_dir}")
