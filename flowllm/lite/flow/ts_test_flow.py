"""Tushare test download flow for ``fl --ts-test``."""

# pylint: disable=missing-function-docstring,too-many-public-methods

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from loguru import logger
from tqdm import tqdm

from ...utils.tushare_data_api import TushareDataApi
from ..cli import BaseConfig, BaseFlow, register

STK_15MIN_TIMES = (
    "09:30:00",
    "09:45:00",
    "10:00:00",
    "10:15:00",
    "10:30:00",
    "10:45:00",
    "11:00:00",
    "11:15:00",
    "11:30:00",
    "13:15:00",
    "13:30:00",
    "13:45:00",
    "14:00:00",
    "14:15:00",
    "14:30:00",
    "14:45:00",
    "15:00:00",
)

RT_K_FIELDS = [
    "ts_code",
    "name",
    "trade_date",
    "pre_close",
    "open",
    "high",
    "close",
    "low",
    "vol",
    "amount",
    "num",
    "ask_price1",
    "ask_volume1",
    "bid_price1",
    "bid_volume1",
    "trade_time",
]

FINA_INDICATOR_FIELDS = """
ts_code ann_date end_date eps dt_eps total_revenue_ps revenue_ps capital_rese_ps
surplus_rese_ps undist_profit_ps extra_item profit_dedt assets_turn op_income
valuechange_income daa retained_earnings diluted2_eps bps ocfps retainedps cfps
netprofit_margin profit_to_gr adminexp_of_gr op_of_gr roe roe_waa roe_dt npta
roe_yearly roe_avg opincome_of_ebt investincome_of_ebt n_op_profit_of_ebt tax_to_ebt
dtprofit_to_profit ocf_to_or ocf_to_opincome capitalized_to_da debt_to_assets
assets_to_eqt dp_assets_to_eqt debt_to_eqt eqt_to_debt ocf_to_debt roa_yearly
roa_dp fixed_assets non_op_profit op_to_ebt nop_to_ebt ocf_to_profit op_to_debt
total_fa_trun profit_to_op q_opincome q_investincome q_dtprofit q_eps
q_netprofit_margin q_profit_to_gr q_adminexp_to_gr q_op_to_gr q_roe q_dt_roe
q_npta q_opincome_to_ebt q_investincome_to_ebt q_dtprofit_to_profit q_ocf_to_sales
q_ocf_to_or basic_eps_yoy dt_eps_yoy cfps_yoy op_yoy ebt_yoy netprofit_yoy
dt_netprofit_yoy ocf_yoy roe_yoy bps_yoy assets_yoy eqt_yoy tr_yoy or_yoy
q_gr_yoy q_gr_qoq q_sales_yoy q_sales_qoq q_op_yoy q_op_qoq q_profit_yoy
q_profit_qoq q_netprofit_yoy q_netprofit_qoq equity_yoy update_flag
""".split()


class TushareConfig(BaseConfig):
    """Configuration for the Tushare test flow."""

    token: str = ""
    timeout: int = 30
    use_proxy: bool = False
    proxy_port: int = 12345
    output_dir: str = "tmp_data/tushare"
    sample_date: str = "20260622"
    premarket_date: str = "20260625"
    stock_st_date: str = "20260625"
    validate_daily_codes: bool = True
    daily_validation_exclude_suffixes: str = ".BJ"
    stk_mins_max_codes: int = 20_000_000
    stk_mins_batch_size: int = 1000
    rt_min_batch_size: int = 999
    rt_min_freq: str = "15MIN"
    rt_min_daily_date: str = "2026-06-22"
    rt_min_daily_workers: int = 10


def _fields(fields: Iterable[str] | str | None = None) -> str:
    if fields is None:
        return ""
    if isinstance(fields, str):
        return fields
    return ",".join(fields)


@register("ts_test")
class TushareFlow(BaseFlow[TushareConfig]):
    """Download the migrated DeepSleep Tushare test APIs in order."""

    output_keys = ["output_dir", "sample_date", "premarket_date", "stock_st_date", "saved_files"]

    def build_steps(self) -> list:
        return [
            self.init_client,
            self.download_trade_cal,
            self.download_stock_basic,
            self.download_namechange,
            self.download_daily,
            self.download_adj_factor,
            self.download_daily_basic,
            self.download_bak_basic,
            self.download_bak_daily,
            self.download_stk_limit,
            self.download_stk_factor,
            self.download_margin_detail,
            self.download_moneyflow,
            self.download_fina_indicator_vip,
            self.download_stk_premarket,
            self.download_stock_st,
            self.download_stk_15min_example,
            self.download_rt_k,
            self.download_rt_min,
            self.download_rt_min_daily,
        ]

    @property
    def output_dir(self) -> Path:
        return Path(self.config.output_dir).expanduser()

    @property
    def sample_date(self) -> str:
        return self.config.sample_date

    @property
    def premarket_date(self) -> str:
        return self.config.premarket_date

    @property
    def stock_st_date(self) -> str:
        return self.config.stock_st_date

    @property
    def client(self) -> TushareDataApi:
        return self.context["ts_client"]

    def init_client(self) -> None:
        self.context["ts_client"] = TushareDataApi(
            token=self.config.token,
            timeout=self.config.timeout,
            use_proxy=self.config.use_proxy,
            proxy_port=self.config.proxy_port,
        )
        self.context.update(
            output_dir=str(self.output_dir),
            sample_date=self.sample_date,
            premarket_date=self.premarket_date,
            stock_st_date=self.stock_st_date,
            saved_files=[],
        )

    def query(self, api_name: str, fields: Iterable[str] | str | None = None, **params) -> pd.DataFrame:
        return self.client.query(api_name=api_name, fields=_fields(fields), **params)

    def save_csv(self, df: pd.DataFrame | None, filename: str) -> None:
        path = self.output_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if df is None or df.empty:
            logger.warning("Empty: {}", path)
            return
        df.to_csv(path, index=False)
        self.context["saved_files"].append(str(path))
        logger.info("Saved {}: {} rows", path, len(df))

    def download_trade_cal(self) -> None:
        self.save_csv(self.query("trade_cal"), "trade_cal.csv")

    def download_stock_basic(self) -> None:
        df = pd.concat(
            [self.query("stock_basic", list_status=status) for status in ("L", "D", "P", "G")],
            ignore_index=True,
        )
        self.save_csv(df, "stock_basic.csv")

    def download_namechange(self) -> None:
        self.save_csv(self.client.query_has_more("namechange"), "namechange.csv")

    def download_daily_api(self, api_name: str, validate_daily_codes: bool | None = None) -> pd.DataFrame:
        date = self.sample_date
        df = self.query(api_name, trade_date=date)
        self.save_csv(df, f"{api_name}/{date}.csv")
        codes = self._extract_ts_codes(df, api_name)
        if api_name == "daily":
            self.context["daily_codes"] = codes
        else:
            should_validate = self.config.validate_daily_codes if validate_daily_codes is None else validate_daily_codes
            if should_validate:
                self.validate_daily_codes(api_name, codes)
        return df

    @staticmethod
    def _extract_ts_codes(df: pd.DataFrame | None, api_name: str) -> list[str]:
        if df is None or df.empty:
            return []
        if "ts_code" not in df.columns:
            raise ValueError(f"{api_name} response missing ts_code column")
        return sorted(df["ts_code"].dropna().astype(str).unique().tolist())

    def validate_daily_codes(self, api_name: str, actual_codes: list[str]) -> None:
        expected_codes = self.context.get("daily_codes")
        if expected_codes is None:
            raise RuntimeError(f"daily_codes not found in context; run download_daily before download_{api_name}")

        missing_codes = sorted(set(self.filter_daily_validation_codes(expected_codes)) - set(actual_codes))
        if missing_codes:
            sample = ", ".join(missing_codes[:20])
            if len(missing_codes) > 20:
                sample = f"{sample}, ..."
            raise RuntimeError(
                f"{api_name} missing {len(missing_codes)} ts_code values for {self.sample_date}: {sample}",
            )

    def filter_daily_validation_codes(self, codes: list[str]) -> list[str]:
        suffixes = [item.strip() for item in self.config.daily_validation_exclude_suffixes.split(",") if item.strip()]
        return [code for code in codes if not suffixes or not code.endswith(tuple(suffixes))]

    def download_daily(self) -> None:
        self.context["daily_df"] = self.download_daily_api("daily", validate_daily_codes=False)

    def download_adj_factor(self) -> None:
        self.download_daily_api("adj_factor")

    def download_daily_basic(self) -> None:
        self.download_daily_api("daily_basic")

    def download_bak_basic(self) -> None:
        self.download_daily_api("bak_basic", validate_daily_codes=False)

    def download_bak_daily(self) -> None:
        self.download_daily_api("bak_daily", validate_daily_codes=False)

    def download_stk_limit(self) -> None:
        self.download_daily_api("stk_limit", validate_daily_codes=True)

    def download_stk_factor(self) -> None:
        self.download_daily_api("stk_factor", validate_daily_codes=True)

    def download_margin_detail(self) -> None:
        self.download_daily_api("margin_detail", validate_daily_codes=False)

    def download_moneyflow(self) -> None:
        self.download_daily_api("moneyflow")

    def download_fina_indicator_vip(self) -> None:
        date = self.sample_date
        df = self.query("fina_indicator_vip", fields=FINA_INDICATOR_FIELDS, ann_date=date)
        self.save_csv(df, f"fina_indicator_vip/{date}.csv")

    def download_stk_premarket(self) -> None:
        date = self.premarket_date
        self.save_csv(self.query("stk_premarket", trade_date=date), f"stk_premarket/{date}.csv")

    def download_stock_st(self) -> None:
        date = self.stock_st_date
        self.save_csv(self.query("stock_st", trade_date=date), f"stock_st/{date}.csv")

    def download_stk_15min_example(self) -> None:
        date = self.sample_date
        daily_df = self.context.get("daily_df")
        if daily_df is None or daily_df.empty or "ts_code" not in daily_df.columns:
            logger.warning("daily returned no ts_code values; skip stk_mins example")
            return

        codes = daily_df["ts_code"].dropna().astype(str).head(self.config.stk_mins_max_codes).tolist()
        df = self.query_stk_15min(date, codes)
        self.validate_daily_codes("stk_15min", self._extract_ts_codes(df, "stk_15min"))
        self.save_csv(df, f"stk_15min/{date}.csv")

    def query_stk_15min(self, date: str, ts_codes: list[str]) -> pd.DataFrame:
        if not ts_codes:
            return pd.DataFrame()

        day = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        frames = []
        for item in STK_15MIN_TIMES:
            trade_time = f"{day} {item}"
            for i in range(0, len(ts_codes), self.config.stk_mins_batch_size):
                logger.info("Downloading batch={} codes for {}", i, trade_time)
                df = self.query(
                    "stk_mins",
                    ts_code=",".join(ts_codes[i : i + self.config.stk_mins_batch_size]),
                    freq="15min",
                    start_date=trade_time,
                    end_date=trade_time,
                )
                if df is not None and not df.empty and "trade_time" in df.columns:
                    df = df[df["trade_time"].astype(str) == trade_time].copy()
                    if not df.empty:
                        frames.append(df)

        if not frames:
            return pd.DataFrame()

        df_all = pd.concat(frames, ignore_index=True).drop_duplicates(["ts_code", "trade_time"], keep="last")
        self.log_grid_gaps(df_all, "ts_code", "trade_time")
        return df_all.sort_values(["trade_time", "ts_code"], ascending=[False, True], ignore_index=True)

    @staticmethod
    def log_grid_gaps(df: pd.DataFrame, code_col: str, time_col: str, label: str = "") -> None:
        codes = df[code_col].unique()
        times = df[time_col].unique()
        expected = len(codes) * len(times)
        if len(df) < expected:
            missing = pd.MultiIndex.from_product(
                [codes, times],
                names=[code_col, time_col],
            ).difference(
                df.set_index([code_col, time_col]).index,
            )
            logger.warning(
                "Data gap{}: {} missing rows, {} codes incomplete out of {}",
                f" ({label})" if label else "",
                expected - len(df),
                len(missing.get_level_values(code_col).unique()),
                len(codes),
            )
        else:
            logger.info(
                "Data complete{}: {} codes x {} times = {} rows",
                f" ({label})" if label else "",
                len(codes),
                len(times),
                len(df),
            )

    def download_rt_k(self) -> None:
        df = self.query("rt_k", fields=RT_K_FIELDS, ts_code="3*.SZ,6*.SH,0*.SZ")
        if df is None or df.empty:
            self.save_csv(df, "rt_k/empty.csv")
            return

        if "vol" in df.columns:
            before = len(df)
            df = df[pd.to_numeric(df["vol"], errors="coerce").fillna(0) > 0].copy()
            if before != len(df):
                logger.warning("Drop {} rt_k rows with vol=0", before - len(df))
        if df.empty:
            self.save_csv(df, "rt_k/empty.csv")
            return

        filename = "rt_k/latest.csv"
        max_time = df["trade_time"].dropna().max()
        if not pd.isna(max_time):
            filename = f"rt_k/{pd.to_datetime(max_time):%Y%m%d_%H%M}.csv"
        self.save_csv(df, filename)
        self.context["rt_k_df"] = df

    def download_rt_min(self) -> None:
        code_df = self.context.get("rt_k_df")
        if code_df is None or code_df.empty or "ts_code" not in code_df.columns:
            logger.warning("rt_k returned no ts_code values; skip rt_min example")
            return

        codes = sorted(code_df["ts_code"].dropna().astype(str).unique())
        frames = []
        for i in range(0, len(codes), self.config.rt_min_batch_size):
            logger.info("Downloading rt_min batch={} codes", i)
            batch = codes[i : i + self.config.rt_min_batch_size]
            df = self.query("rt_min", ts_code=",".join(batch), freq=self.config.rt_min_freq)
            if df is not None and not df.empty:
                frames.append(df)

        if not frames:
            logger.warning("rt_min returned no data")
            return

        now = datetime.now()
        df_all = pd.concat(frames, ignore_index=True)
        if "time" not in df_all.columns:
            raise ValueError("rt_min response missing time column")

        df_all = df_all.drop_duplicates(["ts_code", "time"], keep="last")

        actual_codes = set(df_all["ts_code"].dropna().astype(str))
        missing_codes = sorted(set(codes) - actual_codes)
        if missing_codes:
            sample = ", ".join(missing_codes[:20])
            if len(missing_codes) > 20:
                sample = f"{sample}, ..."
            raise RuntimeError(
                f"rt_min missing {len(missing_codes)} ts_code values from rt_k for {now:%Y-%m-%d}: {sample}",
            )

        extra_codes = sorted(actual_codes - set(codes))
        if extra_codes:
            logger.warning("rt_min returned {} codes not in rt_k: {}", len(extra_codes), ", ".join(extra_codes[:20]))
        time_counts = df_all["time"].astype(str).value_counts().sort_index()
        logger.info(
            "rt_min complete: {} codes from rt_k; {} times, latest={}",
            len(actual_codes),
            len(time_counts),
            time_counts.index[-1],
        )
        self.save_csv(df_all, f"rt_min/{now:%Y%m%d_%H%M}.csv")

    def download_rt_min_daily(self) -> None:
        code_df = self.context.get("rt_k_df")
        if code_df is None or code_df.empty or "ts_code" not in code_df.columns:
            logger.warning("rt_k returned no ts_code values; skip rt_min_daily")
            return

        codes = sorted(code_df["ts_code"].dropna().astype(str).unique())

        def fetch(code: str) -> pd.DataFrame | None:
            df = self.query(
                "rt_min_daily",
                ts_code=code,
                date_str=self.config.rt_min_daily_date,
                freq="15MIN",
            )
            if df is not None and not df.empty and "ts_code" not in df.columns:
                df["ts_code"] = code
            return df

        frames = []
        with ThreadPoolExecutor(max_workers=self.config.rt_min_daily_workers) as pool:
            futures = {pool.submit(fetch, code): code for code in codes}
            for future in tqdm(as_completed(futures), total=len(codes), desc="rt_min_daily"):
                df = future.result()
                if df is not None and not df.empty:
                    frames.append(df)

        if not frames:
            logger.warning("rt_min_daily returned no data")
            return

        df_all = pd.concat(frames, ignore_index=True).drop_duplicates(
            ["ts_code", "time"],
            keep="last",
        )
        df_check = df_all[~df_all["time"].astype(str).str.endswith("09:30:00")]
        self.log_grid_gaps(df_check, "ts_code", "time", "excluding 09:30")
        self.save_csv(df_all, f"rt_min_daily/{self.config.rt_min_daily_date.replace('-', '')}.csv")
