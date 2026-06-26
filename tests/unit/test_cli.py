"""Unit tests for CLI call_server function."""

from flowllm import application as flowllm_module


def test_call_server_passes_client_kwargs_to_client(monkeypatch, capsys):
    """Verify call_server separates client kwargs from action payload."""
    seen = {}

    class FakeClient:
        """Mock client for testing call_server."""

        def __init__(self, **kwargs):
            seen["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

        async def __call__(self, action: str, **kwargs):
            seen["action"] = action
            seen["payload"] = kwargs
            yield "ok"

    monkeypatch.setattr(flowllm_module.R, "get", lambda component_type, backend: FakeClient)

    async def run():
        await flowllm_module.call_server(
            "search",
            backend="http",
            host="127.0.0.2",
            port=2444,
            timeout=1.5,
            query="hello",
        )

    import asyncio

    asyncio.run(run())

    assert seen["client_kwargs"] == {"host": "127.0.0.2", "port": 2444, "timeout": 1.5}
    assert seen["action"] == "search"
    assert seen["payload"] == {"query": "hello"}
    assert capsys.readouterr().out == "ok\n"
