"""Unit tests for the Tushare data API helper."""

import pytest

from flowllm.utils import tushare_data_api
from flowllm.utils.tushare_data_api import TushareDataApi


class FakeResponse:
    """Minimal HTTP response object for Tushare tests."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class FakeClient:
    """HTTP client that returns queued payloads."""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.requests = []
        self.closed = False

    def post(self, url, json, timeout):
        self.requests.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse(self.payloads.pop(0))

    def close(self):
        self.closed = True


def test_tushare_query_builds_payload(monkeypatch):
    """Verify query sends the expected payload and returns a DataFrame."""
    monkeypatch.setattr(tushare_data_api, "load_env", lambda: {})
    client = FakeClient(
        [
            {
                "code": 0,
                "data": {"fields": ["ts_code", "close"], "items": [["000001.SZ", 10.5]]},
            }
        ]
    )

    api = TushareDataApi(token="token", timeout=5, http_url="http://example.test/dataapi", client=client)
    frame = api.query("daily", fields="ts_code,close", trade_date="20260626")

    assert frame.to_dict("records") == [{"ts_code": "000001.SZ", "close": 10.5}]
    assert client.requests == [
        {
            "url": "http://example.test/dataapi/daily",
            "json": {
                "api_name": "daily",
                "token": "token",
                "params": {
                    "trade_date": "20260626",
                    "ts_type_name": "http://example.test/dataapi",
                },
                "fields": "ts_code,close",
            },
            "timeout": 5,
        }
    ]


def test_tushare_query_rejects_incomplete_result(monkeypatch):
    """Verify query directs callers to the pagination helper."""
    monkeypatch.setattr(tushare_data_api, "load_env", lambda: {})
    client = FakeClient([{"code": 0, "data": {"fields": ["x"], "items": [[1]], "has_more": True}}])
    api = TushareDataApi(token="token", client=client)

    with pytest.raises(RuntimeError, match="query_has_more"):
        api.query("daily")


def test_tushare_query_has_more_merges_pages(monkeypatch):
    """Verify paginated requests advance offset with overlap and de-duplicate rows."""
    monkeypatch.setattr(tushare_data_api, "load_env", lambda: {})
    client = FakeClient(
        [
            {
                "code": 0,
                "data": {"fields": ["x"], "items": [[1], [2]], "has_more": True},
            },
            {
                "code": 0,
                "data": {"fields": ["x"], "items": [[2], [3]], "has_more": False},
            },
        ]
    )
    api = TushareDataApi(token="token", client=client)

    frame = api.query_has_more("daily", limit=2, overlap=0.5)

    assert frame.to_dict("records") == [{"x": 1}, {"x": 2}, {"x": 3}]
    assert client.requests[0]["json"]["params"]["offset"] == 0
    assert client.requests[1]["json"]["params"]["offset"] == 1


def test_tushare_query_has_more_validates_options(monkeypatch):
    """Verify invalid pagination options fail early."""
    monkeypatch.setattr(tushare_data_api, "load_env", lambda: {})
    api = TushareDataApi(token="token", client=FakeClient([]))

    with pytest.raises(ValueError, match="limit"):
        api.query_has_more("daily", limit=0)

    with pytest.raises(ValueError, match="overlap"):
        api.query_has_more("daily", overlap=1)


def test_tushare_data_api_requires_token(monkeypatch):
    """Verify missing token fails before creating requests."""
    monkeypatch.setattr(tushare_data_api, "load_env", lambda: {})
    monkeypatch.setattr(tushare_data_api, "_get_token", lambda: "")

    with pytest.raises(RuntimeError, match="token"):
        TushareDataApi()
