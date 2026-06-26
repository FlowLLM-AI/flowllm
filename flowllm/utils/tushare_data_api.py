"""Tushare Pro data client."""

from typing import Any

import pandas as pd
import requests
from tushare import get_token
from tushare.pro.client import DataApi


class TushareDataApiError(RuntimeError):
    """Raised when the Tushare API returns an error response."""


class TushareDataApi(DataApi):
    """Tushare Pro data client."""

    _DEFAULT_HTTP_URL = "http://api.waditu.com/dataapi"

    def __init__(
        self,
        token: str | None = "",
        timeout: int | float = 30,
        use_proxy: bool = False,
        proxy_port: int = 12345,
        session: requests.Session | None = None,
    ) -> None:
        """
        Parameters
        ----------
        token: str
            API token for authentication. When empty, use the official
            fallback lookup from environment variables or ``~/tk.csv``.
        timeout: int
            Request timeout in seconds.
        use_proxy: bool
            Whether to use a local SOCKS5 proxy.
        proxy_port: int
            Local SOCKS5 proxy port. Defaults to 12345.
        session: requests.Session
            Optional requests session for connection reuse or custom request
            settings.
        """
        token = token or get_token()
        if not token:
            raise TushareDataApiError("api init error.")

        super().__init__(token=token, timeout=timeout)
        self._token = token
        self._timeout = timeout
        self._proxy_port = proxy_port
        self._http_url = getattr(self, "_DataApi__http_url", self._DEFAULT_HTTP_URL)
        self._session = session or requests.Session()
        if use_proxy:
            self._session.proxies.update(dict.fromkeys(("http", "https"), self._proxy_url))

    @property
    def _proxy_url(self) -> str:
        """Return the local SOCKS5 proxy URL."""
        return f"socks5h://127.0.0.1:{self._proxy_port}"

    def query(self, api_name: str, fields: str = "", **kwargs: Any) -> pd.DataFrame:
        """Query one Tushare API endpoint and return the response as a DataFrame."""
        kwargs.setdefault("ts_type_name", self._http_url)
        payload = {
            "api_name": api_name,
            "token": self._token,
            "params": kwargs,
            "fields": fields,
        }

        response = self._session.post(f"{self._http_url}/{api_name}", json=payload, timeout=self._timeout)
        if not response:
            return pd.DataFrame()

        result = response.json()
        if result["code"] != 0:
            raise TushareDataApiError(result["msg"])

        data = result["data"]
        if data.get("has_more"):
            raise TushareDataApiError("Tushare API returned has_more=True; query result is incomplete")
        return pd.DataFrame(data["items"], columns=data["fields"])

    def query_has_more(
        self,
        api_name: str,
        fields: str = "",
        limit: int = 20000,
        overlap: float = 0.2,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Query all pages for endpoints that may return ``has_more=True``."""
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if not 0 <= overlap < 1:
            raise ValueError("overlap must be in [0, 1)")

        offset = 0
        df_list = []
        while True:
            params = {**kwargs, "offset": offset, "limit": limit}
            params.setdefault("ts_type_name", self._http_url)
            payload = {
                "api_name": api_name,
                "token": self._token,
                "params": params,
                "fields": fields,
            }
            response = self._session.post(f"{self._http_url}/{api_name}", json=payload, timeout=self._timeout)
            if not response:
                return pd.DataFrame()

            result = response.json()
            if result["code"] != 0:
                raise TushareDataApiError(result["msg"])

            data = result["data"]
            df = pd.DataFrame(data["items"], columns=data["fields"])
            df_list.append(df)
            if not data.get("has_more") or df.empty:
                break
            step = max(1, int(len(df) * (1 - overlap)))
            offset += step

        df_list = [df for df in df_list if not df.empty]
        if not df_list:
            return pd.DataFrame()
        return pd.concat(df_list, ignore_index=True).drop_duplicates(ignore_index=True)
