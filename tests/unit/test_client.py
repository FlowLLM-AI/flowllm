"""Unit tests for client abstractions."""

# pylint: disable=protected-access,invalid-overridden-method

import asyncio
import json

import pytest

from flowllm.components.client import BaseClient, HttpClient, MCPClient
from flowllm.constants import FLOWLLM_DEFAULT_HOST, FLOWLLM_DEFAULT_PORT, FLOWLLM_SERVICE_INFO


class _FakeClient(BaseClient):
    """Concrete BaseClient for exercising wrapper behavior."""

    def __init__(self, actions=None, **kwargs):
        super().__init__(**kwargs)
        self.actions = actions or [{"action": "search"}]
        self.payloads = []

    async def list_actions(self):
        return self.actions

    async def _execute(self, action: str, payload: dict):
        self.payloads.append((action, payload))
        yield "chunk"


def test_base_client_list_action_returns_pretty_json():
    """The synthetic list action uses list_actions instead of _execute."""

    async def run():
        client = _FakeClient(actions=[{"action": "health_check", "method": "GET"}])
        chunks = [chunk async for chunk in client("list")]
        assert json.loads(chunks[0]) == [{"action": "health_check", "method": "GET"}]
        assert not client.payloads

    asyncio.run(run())


def test_base_client_delegates_non_list_actions():
    """Regular actions pass through to _execute with kwargs as payload."""

    async def run():
        client = _FakeClient()
        assert [chunk async for chunk in client("search", query="hi")] == ["chunk"]
        assert client.payloads == [("search", {"query": "hi"})]

    asyncio.run(run())


def test_http_client_reads_service_info_from_environment(monkeypatch):
    """HTTP client host/port default from FLOWLLM_SERVICE_INFO when present."""
    monkeypatch.setenv(FLOWLLM_SERVICE_INFO, json.dumps({"host": "10.0.0.1", "port": 8123}))

    client = HttpClient()

    assert client.base_url == "http://10.0.0.1:8123"


def test_http_client_falls_back_on_invalid_service_info(monkeypatch):
    """Invalid service info is ignored in favor of built-in defaults."""
    monkeypatch.setenv(FLOWLLM_SERVICE_INFO, "not-json")

    client = HttpClient()

    assert client.base_url == f"http://{FLOWLLM_DEFAULT_HOST}:{FLOWLLM_DEFAULT_PORT}"


def test_http_client_format_for_display_handles_response_envelope():
    """Response envelopes render answer first with status and metadata."""
    rendered = HttpClient._format_for_display(
        json.dumps({"answer": "done", "success": True, "metadata": {"cost": 1}, "extra": "x"}),
    )

    assert rendered.splitlines()[0] == "done"
    assert "\u2705" in rendered
    assert '{"cost": 1}' in rendered
    assert '"extra": "x"' in rendered


def test_mcp_client_rejects_unknown_transport():
    """Unsupported MCP transport names fail during construction."""
    with pytest.raises(ValueError, match="Unknown transport"):
        MCPClient(transport="websocket")
