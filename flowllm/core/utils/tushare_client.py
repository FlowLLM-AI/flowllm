"""Tushare API client."""

import os
from typing import Optional

import pandas as pd
import requests


class TushareClient:
    """Tushare API client."""

    def __init__(
        self,
        request_limit_size: int = 10000,
        timeout: float = 30.0,
    ):
        """Initialize client.

        Args:
            request_limit_size: Max records per request. Default 10000.
            timeout: Request timeout in seconds. Default 30.0.
        """
        self.token = os.getenv("TUSHARE_API_TOKEN")
        if not self.token:
            raise ValueError("TUSHARE_API_TOKEN not set")

        self.url = "http://api.waditu.com/dataapi"
        self.request_limit_size = request_limit_size
        self.timeout = timeout

    def request(
        self,
        api_name: str,
        fields: Optional[list[str]] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """Request data from API.

        Args:
            api_name: API endpoint name.
            fields: Optional field list. None returns all fields.
            **kwargs: Additional API parameters.

        Returns:
            DataFrame with requested data.
        """
        data_dict = {
            "api_name": api_name,
            "token": self.token,
            "params": {
                "offset": 0,
                "limit": self.request_limit_size,
                **kwargs,
            },
        }
        if fields:
            data_dict["fields"] = fields

        df_list = []
        offset = 0

        while True:
            data_dict["params"]["offset"] = offset
            response = requests.post(
                url=self.url,
                json=data_dict,
                timeout=self.timeout,
            )
            df, has_more = self._parse_response(response)
            df_list.append(df)
            offset += len(df)

            if not has_more or len(df) == 0:
                break

        if len(df_list) == 0:
            raise RuntimeError(f"No data returned from API: {api_name}")

        if len(df_list) == 1:
            return df_list[0]
        return pd.concat(df_list, axis=0, ignore_index=True)

    @staticmethod
    def _parse_response(response: requests.Response) -> tuple[pd.DataFrame, bool]:
        """Parse API response to DataFrame.

        Returns:
            (DataFrame, has_more)
        """
        response.raise_for_status()
        data = response.json()

        if not data:
            return pd.DataFrame(), False

        if data.get("code") != 0:
            raise ValueError(f"API error: {data.get('msg', 'Unknown error')}")

        data_dict = data.get("data", {})
        items = data_dict.get("items", [])
        fields = data_dict.get("fields", [])
        has_more = data_dict.get("has_more", False)

        if not items or not fields:
            return pd.DataFrame(), False

        return pd.DataFrame(items, columns=fields), has_more
