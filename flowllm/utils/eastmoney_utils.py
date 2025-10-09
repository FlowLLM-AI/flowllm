import math
import os

import akshare as ak
import pandas as pd
import requests


def get_ah_mapping() -> pd.DataFrame:
    EAST_MONEY_COOKIE = os.getenv("EAST_MONEY_COOKIE")
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "np": "1",
        "fltt": "1",
        "invt": "2",
        "fs": "b:DLMK0101",
        "fields": "f193,f191,f192,f12,f13,f14,f1,f2,f4,f3,f152,f186,f190,f187,f189,f188",
        "fid": "f3",
        "pn": "1",
        "pz": "100",
        "po": "1",
        "dect": "1",
        "wbp2u": "|0|0|0|web",
    }
    headers = {}
    if EAST_MONEY_COOKIE:
        headers["Cookie"] = EAST_MONEY_COOKIE
    temp_df = fetch_paginated_data(url, base_params=params, headers=headers)

    columns_mapping = {
        "f193": "name",
        "f12": "hk_code",
        "f2": "hk_price",
        "f3": "hk_pct_chg",
        "f191": "a_code",
        "f186": "a_price",
        "f187": "a_pct_chg",
        "f189": "ah_price_ratio",
        "f188": "ah_premium_ratio",
    }

    temp_df = temp_df.rename(columns=columns_mapping).loc[:, list(columns_mapping.values())]
    temp_df["hk_price"] = pd.to_numeric(temp_df["hk_price"], errors="coerce") / 1000
    temp_df["hk_pct_chg"] = pd.to_numeric(temp_df["hk_pct_chg"], errors="coerce") / 100
    temp_df["a_price"] = pd.to_numeric(temp_df["a_price"], errors="coerce") / 100
    temp_df["a_pct_chg"] = pd.to_numeric(temp_df["a_pct_chg"], errors="coerce") / 100
    temp_df["ah_price_ratio"] = pd.to_numeric(temp_df["ah_price_ratio"], errors="coerce") / 100
    temp_df["ah_premium_ratio"] = pd.to_numeric(temp_df["ah_premium_ratio"], errors="coerce") / 100
    return temp_df


def fetch_paginated_data(url: str, base_params: dict, headers: dict = None, timeout: int = 15) -> pd.DataFrame:
    params = base_params.copy()
    response = requests.get(url, params=params, headers=headers, timeout=timeout)
    data_json = response.json()
    items_per_page = len(data_json["data"]["diff"])
    total_pages = math.ceil(data_json["data"]["total"] / items_per_page)
    page_dataframes = [pd.DataFrame(data_json["data"]["diff"])]

    # Get remaining page data
    for page in range(2, total_pages + 1):
        params.update({"pn": page})
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        data_json = response.json()
        page_dataframe = pd.DataFrame(data_json["data"]["diff"])
        page_dataframes.append(page_dataframe)

    # Merge all data
    merged_dataframe = pd.concat(page_dataframes, ignore_index=True)
    merged_dataframe["f3"] = pd.to_numeric(merged_dataframe["f3"], errors="coerce")
    merged_dataframe.sort_values(by=["f3"], ascending=False, inplace=True, ignore_index=True)
    return merged_dataframe


def get_a_stock_df(code: str,
                   period: str = "daily",
                   start_date: str = "20160101",
                   end_date: str = "20300101",
                   adjust: str = "hfq",
                   timeout: float = None) -> pd.DataFrame:
    EAST_MONEY_COOKIE = os.getenv("EAST_MONEY_COOKIE")

    market_code = 1 if code.startswith("6") else 0
    adjust_dict = {"qfq": "1", "hfq": "2", "": "0"}
    period_dict = {"daily": "101", "weekly": "102", "monthly": "103"}
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": period_dict[period],
        "fqt": adjust_dict[adjust],
        "secid": f"{market_code}.{code}",
        "beg": start_date,
        "end": end_date,
    }
    headers = {}
    if EAST_MONEY_COOKIE:
        headers["Cookie"] = EAST_MONEY_COOKIE
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    data_json = r.json()
    if not (data_json["data"] and data_json["data"]["klines"]):
        return pd.DataFrame()

    a_hist_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    a_hist_df["code"] = code
    a_hist_df.columns = [
        "date",
        "open",
        "close",
        "high",
        "low",
        "vol",
        "amount",
        "swing",
        "chg_pct",
        "change",
        "turnover_ratio",
        "code",
    ]
    a_hist_df["date"] = pd.to_datetime(a_hist_df["date"], errors="coerce").dt.date
    a_hist_df["open"] = pd.to_numeric(a_hist_df["open"], errors="coerce")
    a_hist_df["close"] = pd.to_numeric(a_hist_df["close"], errors="coerce")
    a_hist_df["high"] = pd.to_numeric(a_hist_df["high"], errors="coerce")
    a_hist_df["low"] = pd.to_numeric(a_hist_df["low"], errors="coerce")
    a_hist_df["vol"] = pd.to_numeric(a_hist_df["vol"], errors="coerce")
    a_hist_df["amount"] = pd.to_numeric(a_hist_df["amount"], errors="coerce")
    a_hist_df["swing"] = pd.to_numeric(a_hist_df["swing"], errors="coerce")
    a_hist_df["chg_pct"] = pd.to_numeric(a_hist_df["chg_pct"], errors="coerce")
    a_hist_df["change"] = pd.to_numeric(a_hist_df["change"], errors="coerce")
    a_hist_df["turnover_ratio"] = pd.to_numeric(a_hist_df["turnover_ratio"], errors="coerce")
    return a_hist_df


def get_hk_stock_df(code: str,
                    period: str = "daily",
                    start_date: str = "20160101",
                    end_date: str = "20300101",
                    adjust: str = "hfq",
                    timeout: float = None) -> pd.DataFrame:
    EAST_MONEY_COOKIE = os.getenv("EAST_MONEY_COOKIE")

    adjust_dict = {"qfq": "1", "hfq": "2", "": "0"}
    period_dict = {"daily": "101", "weekly": "102", "monthly": "103"}
    url = "https://33.push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": period_dict[period],
        "fqt": adjust_dict[adjust],
        "secid": f"116.{code}",
        "beg": start_date,
        "end": end_date,
    }
    headers = {}
    if EAST_MONEY_COOKIE:
        headers["Cookie"] = EAST_MONEY_COOKIE
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    data_json = r.json()
    if not (data_json["data"] and data_json["data"]["klines"]):
        return pd.DataFrame()

    hk_hist_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    hk_hist_df["code"] = code
    hk_hist_df.columns = [
        "date",
        "open",
        "close",
        "high",
        "low",
        "vol",
        "amount",
        "swing",
        "chg_pct",
        "change",
        "turnover_ratio",
        "code",
    ]

    hk_hist_df["date"] = pd.to_datetime(hk_hist_df["date"], errors="coerce").dt.date
    hk_hist_df["open"] = pd.to_numeric(hk_hist_df["open"], errors="coerce")
    hk_hist_df["close"] = pd.to_numeric(hk_hist_df["close"], errors="coerce")
    hk_hist_df["high"] = pd.to_numeric(hk_hist_df["high"], errors="coerce")
    hk_hist_df["low"] = pd.to_numeric(hk_hist_df["low"], errors="coerce")
    hk_hist_df["vol"] = pd.to_numeric(hk_hist_df["vol"], errors="coerce")
    hk_hist_df["amount"] = pd.to_numeric(hk_hist_df["amount"], errors="coerce")
    hk_hist_df["swing"] = pd.to_numeric(hk_hist_df["swing"], errors="coerce")
    hk_hist_df["chg_pct"] = pd.to_numeric(hk_hist_df["chg_pct"], errors="coerce")
    hk_hist_df["change"] = pd.to_numeric(hk_hist_df["change"], errors="coerce")
    hk_hist_df["turnover_ratio"] = pd.to_numeric(hk_hist_df["turnover_ratio"], errors="coerce")
    return hk_hist_df


def get_forex_df(code: str = "HKDCNYC",
                 start_date: str = "20160101",
                 end_date: str = "20300101",
                 timeout: float = None) -> pd.DataFrame:
    EAST_MONEY_COOKIE = os.getenv("EAST_MONEY_COOKIE")
    code_market_map = {
        "HKDCNYC": 120,
        "USDCNYC": 120,
    }

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    market_code = code_market_map[code]
    params = {
        "secid": f"{market_code}.{code}",
        "klt": "101",
        "fqt": "1",
        "beg": start_date,
        "end": end_date,
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64",
        "ut": "f057cbcbce2a86e2866ab8877db1d059",
        "forcect": 1,
    }
    headers = {}
    if EAST_MONEY_COOKIE:
        headers["Cookie"] = EAST_MONEY_COOKIE
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    data_json = r.json()
    if not (data_json["data"] and data_json["data"]["klines"]):
        return pd.DataFrame()

    forex_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    forex_df["code"] = data_json["data"]["code"]
    forex_df["name"] = data_json["data"]["name"]
    forex_df.columns = [
        "date",
        "open",
        "close",
        "high",
        "low",
        "-",
        "-",
        "swing",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "code",
        "name",
    ]
    forex_df = forex_df[
        [
            "date",
            "code",
            "name",
            "open",
            "close",
            "high",
            "low",
            "swing",
        ]
    ]
    forex_df["date"] = pd.to_datetime(forex_df["date"], errors="coerce").dt.date
    forex_df["open"] = pd.to_numeric(forex_df["open"], errors="coerce")
    forex_df["close"] = pd.to_numeric(forex_df["close"], errors="coerce")
    forex_df["high"] = pd.to_numeric(forex_df["high"], errors="coerce")
    forex_df["low"] = pd.to_numeric(forex_df["low"], errors="coerce")
    forex_df["swing"] = pd.to_numeric(forex_df["swing"], errors="coerce")
    return forex_df


def get_history_dividend_detail(code: str):
    result = {}
    df = ak.stock_history_dividend_detail(symbol=code, indicator="分红")
    if df is not None and len(df) > 0:
        result["fh_anno"] = [str(x) for x in df.loc[:, "公告日期"].tolist()]
        result["fh_prog"] = [str(x) for x in df.loc[:, "除权除息日"].tolist()]
    return result

def main():
    # print(os.getenv("EAST_MONEY_COOKIE"))
    #
    # ah_mapping_df = get_ah_mapping()
    # print(ah_mapping_df)
    #
    # a_stock_df = get_a_stock_df("000001")
    # print(a_stock_df)
    #
    # hk_stock_df = get_hk_stock_df("01810")
    # print(hk_stock_df)
    #
    # forex_hist_em_df = get_forex_df(code="HKDCNYC")
    # print(forex_hist_em_df)

    # df = get_history_dividend_detail("300750")
    df = get_history_dividend_detail("000001")
    print(df)

if __name__ == "__main__":
    from flowllm.utils.common_utils import load_env

    load_env()

    main()
