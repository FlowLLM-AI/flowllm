import os
from pathlib import Path
from typing import List

import pandas as pd
import requests
from loguru import logger


class TushareClient:

    def __init__(self, enable_cache: bool = False):
        self.token: str = os.getenv("TUSHARE_API_TOKEN")
        self.url: str = "http://api.waditu.com/dataapi"
        self.request_limit_size: int = 10000
        self.enable_cache: bool = enable_cache
        if self.enable_cache:
            Path("cache").mkdir(exist_ok=True)

    @staticmethod
    def save_df(df: pd.DataFrame, name: str):
        df.to_csv(f"cache/{name}.csv", index=False)

    @staticmethod
    def load_df(name: str) -> pd.DataFrame:
        return pd.read_csv(f"cache/{name}.csv")

    @staticmethod
    def exist_df(name: str):
        return Path(f"cache/{name}.csv").exists()

    def request(self, api_name: str = "", fields: List[str] = None, **kwargs):
        key = "_".join([api_name] + list(kwargs.values()))
        if self.enable_cache and self.exist_df(key):
            return self.load_df(key)

        data_dict: dict = {
            "api_name": api_name,
            "token": self.token,
            "params": {
                "offset": 0,
                "limit": self.request_limit_size,
                **kwargs,
            }
        }
        if fields:
            data_dict["fields"] = fields

        has_more = True
        df_list: List[pd.DataFrame] = []
        while has_more:
            response = requests.post(json=data_dict, url=self.url, timeout=30)
            df, has_more = self.parse_response(response)
            data_dict["params"]["offset"] += len(df)
            df_list.append(df)

        if len(df_list) < 1:
            raise RuntimeError

        elif len(df_list) == 1:
            df = df_list[0]
            if self.enable_cache:
                self.save_df(df, key)
            return df

        else:
            # logger.info(f"api_name={api_name} concat {len(df_list)} df list")
            df = pd.concat(df_list, axis=0).reset_index(drop=True)
            if self.enable_cache:
                self.save_df(df, key)
            return df

    @staticmethod
    def parse_response(response: requests.Response):
        response.raise_for_status()
        response_json = response.json()
        if response_json:
            if response_json["code"] != 0:
                raise Exception(response_json["msg"])

            data = response_json["data"]
            has_more: bool = data["has_more"]
            return pd.DataFrame(data["items"], columns=data["fields"]), has_more

        else:
            return pd.DataFrame(), False


def main():
    from flowllm.utils.common_utils import load_env
    load_env()

    client = TushareClient()
    # df: pd.DataFrame = client.request(api_name="fx_obasic", classify="FX")
    df1: pd.DataFrame = client.request(api_name="fx_daily", ts_code='USDCNH.FXCM')
    logger.info(df1)
    df2: pd.DataFrame = client.request(api_name="fx_daily", ts_code='USDHKD.FXCM')
    logger.info(df2)

    cnh_price = df1.loc[df1.index[-1], "bid_close"]
    hkd_price = df2.loc[df2.index[-1], "bid_close"]
    print(cnh_price, hkd_price, cnh_price / hkd_price)


if __name__ == "__main__":
    main()
