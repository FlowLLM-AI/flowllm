"""Unit tests for service discovery helpers."""

# pylint: disable=protected-access

import pytest

from flowllm.constants import FLOWLLM_DEFAULT_HOST, FLOWLLM_DEFAULT_PORT
from flowllm.utils import service_utils


def test_pid_on_port_returns_first_pid(monkeypatch):
    """Only the first lsof result is used."""
    monkeypatch.setattr(service_utils, "_sh", lambda _cmd: "123\n456\n")

    assert service_utils._pid_on_port(8080) == 123


def test_scan_flowllm_procs_extracts_host_and_port(monkeypatch):
    """flowllm start process args are parsed for service host and port."""
    monkeypatch.setattr(
        service_utils,
        "_sh",
        lambda _cmd: (
            "111 flowllm start service.host=0.0.0.0 service.port=9000\n"
            "222 python -m flowllm start\n"
            "bad not-a-pid\n"
        ),
    )

    assert service_utils._scan_flowllm_procs() == [
        (111, "0.0.0.0", 9000),
        (222, FLOWLLM_DEFAULT_HOST, FLOWLLM_DEFAULT_PORT),
    ]


def test_precheck_start_returns_false_when_flowllm_already_running(monkeypatch, capsys):
    """Existing FlowLLM instance prevents a second start."""

    async def fake_find_flowllm(host, port):
        assert (host, port) == ("127.0.0.9", 7777)
        return "flowllm"

    monkeypatch.setattr(service_utils, "find_flowllm", fake_find_flowllm)

    assert service_utils.precheck_start({"host": "127.0.0.9", "port": "7777"}) is False
    assert "flowllm already running at 127.0.0.9:7777" in capsys.readouterr().out


def test_precheck_start_exits_when_port_occupied(monkeypatch, capsys):
    """Non-FlowLLM listeners on the requested port are reported as errors."""

    async def fake_find_flowllm(_host, _port):
        return "occupied"

    monkeypatch.setattr(service_utils, "find_flowllm", fake_find_flowllm)

    with pytest.raises(SystemExit) as exc:
        service_utils.precheck_start({"port": 8888})

    assert exc.value.code == 1
    assert "port 8888 occupied" in capsys.readouterr().err
