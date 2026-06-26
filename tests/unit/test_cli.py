"""Unit tests for CLI call_server function."""

from flowllm import application as flowllm_module
from flowllm.lite import cli as lite_cli
from flowllm.utils import env_utils


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


def test_lite_main_loads_env_at_start(monkeypatch, tmp_path, capsys):
    """Verify lite CLI loads .env before handling arguments."""
    (tmp_path / ".env").write_text("FLOWLLM_LITE_TEST_ENV=loaded\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FLOWLLM_LITE_TEST_ENV", raising=False)
    monkeypatch.setattr(env_utils, "_LOADED", False)
    monkeypatch.setattr(env_utils, "_LOADED_VALUES", {})

    lite_cli.main(["--help"])

    assert capsys.readouterr().out.startswith("Usage: fl")
    assert env_utils.os.environ["FLOWLLM_LITE_TEST_ENV"] == "loaded"
