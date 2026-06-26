"""Small Tushare Pro data client."""

from typing import Any

import httpx

from .env_utils import load_env


class TushareDataApi:
    """Minimal Tushare Pro client with explicit pagination support."""

    DEFAULT_HTTP_URL = "http://api.waditu.com/dataapi"

    def __init__(
        self,
        token: str | None = "",
        timeout: int | float = 30,
        http_url: str = DEFAULT_HTTP_URL,
        client: httpx.Client | None = None,
    ) -> None:
        load_env()
        self._token = token or _get_token()
        if not self._token:
            raise RuntimeError("Tushare API token is required.")

        self._timeout = timeout
        self._http_url = http_url.rstrip("/")
        self._client = client or httpx.Client()
        self._owns_client = client is None

    def close(self) -> None:
        """Close the owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "TushareDataApi":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def query(self, api_name: str, fields: str = "", **kwargs: Any):
        """Query one Tushare API endpoint and fail if the response is incomplete."""
        params = _with_ts_type_name(kwargs, self._http_url)
        data = self._request(api_name, fields, params)
        if data.get("has_more"):
            raise RuntimeError("Tushare API returned has_more=True; use query_has_more().")
        return _to_dataframe(data)

    def query_has_more(
        self,
        api_name: str,
        fields: str = "",
        limit: int = 20000,
        overlap: float = 0.2,
        **kwargs: Any,
    ):
        """Query all pages for endpoints that may return has_more=True."""
        if limit <= 0:
            raise ValueError("limit must be greater than 0.")
        if not 0 <= overlap < 1:
            raise ValueError("overlap must be in [0, 1).")

        offset = 0
        frames = []
        while True:
            params = _with_ts_type_name({**kwargs, "offset": offset, "limit": limit}, self._http_url)
            data = self._request(api_name, fields, params)
            frame = _to_dataframe(data)
            frames.append(frame)
            if not data.get("has_more") or frame.empty:
                break
            offset += max(1, int(len(frame) * (1 - overlap)))

        frames = [frame for frame in frames if not frame.empty]
        if not frames:
            return _empty_dataframe()

        pd = _pandas()
        return pd.concat(frames, ignore_index=True).drop_duplicates(ignore_index=True)

    def _request(self, api_name: str, fields: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "api_name": api_name,
            "token": self._token,
            "params": params,
            "fields": fields,
        }
        response = self._client.post(f"{self._http_url}/{api_name}", json=payload, timeout=self._timeout)
        response.raise_for_status()
        result = response.json()
        if result.get("code") != 0:
            raise RuntimeError(result.get("msg", "Tushare API request failed."))
        return result.get("data") or {"fields": [], "items": []}


def _get_token() -> str:
    """Resolve a token from env first, then Tushare's own token storage."""
    import os

    token = os.environ.get("TUSHARE_TOKEN") or os.environ.get("TS_TOKEN")
    if token:
        return token

    try:
        from tushare import get_token
    except ImportError:
        return ""
    return get_token() or ""


def _with_ts_type_name(params: dict[str, Any], http_url: str) -> dict[str, Any]:
    params.setdefault("ts_type_name", http_url)
    return params


def _pandas():
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required to use TushareDataApi.") from exc
    return pd


def _to_dataframe(data: dict[str, Any]):
    pd = _pandas()
    return pd.DataFrame(data.get("items") or [], columns=data.get("fields") or [])


def _empty_dataframe():
    pd = _pandas()
    return pd.DataFrame()
