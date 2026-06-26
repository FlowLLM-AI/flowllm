"""Remote command execution client flow for ``fl --remote-client``."""

import os
import sys
from pathlib import Path
from typing import Literal

import requests
from loguru import logger

from ..cli import BaseConfig, BaseFlow, register


class RemoteClientConfig(BaseConfig):
    """Configuration for the remote execution client."""

    action: Literal["exec", "ping", "tasks", "kill", "kill_all"] = "exec"
    host: str = ""
    port: int = 8765
    timeout: int = 3600
    command: str = ""
    command_file: str = ""
    python_file: str = ""
    status: str = ""
    tail: int = 30
    task_id: int = 0


def _host(host: str) -> str:
    host = host or os.environ.get("DEFAULT_REMOTE_HOST_ENV", "")
    if not host:
        raise ValueError("Remote host is required. Set DEFAULT_REMOTE_HOST_ENV or pass --host.")
    return host


def _get(host: str, port: int, path: str, **params):
    params = {k: v for k, v in params.items() if v not in (None, "")}
    resp = requests.get(f"http://{host}:{port}{path}", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _post(host: str, port: int, path: str, timeout: int = 30):
    resp = requests.post(f"http://{host}:{port}{path}", timeout=timeout)
    if resp.status_code == 404:
        return {"status": "error", "detail": resp.text}
    resp.raise_for_status()
    return resp.json()


def stream_exec(host: str, port: int, payload: dict, timeout: int) -> None:
    """Stream a remote command response to stdout."""
    try:
        resp = requests.post(f"http://{host}:{port}/exec", json=payload, stream=True, timeout=(10, timeout + 30))
        resp.raise_for_status()
        for chunk in resp.iter_content(chunk_size=None):
            if chunk:
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
    except requests.exceptions.ChunkedEncodingError as exc:
        logger.error("connection interrupted; remote process may still be running, use --action tasks")
        raise SystemExit(1) from exc
    except requests.exceptions.ConnectionError as exc:
        logger.error("cannot connect to {}:{}", host, port)
        logger.error("{}", exc)
        logger.info("for multi-line commands, prefer --python-file")
        raise SystemExit(1) from exc
    except requests.exceptions.RequestException as exc:
        logger.error("request failed: {}: {}", type(exc).__name__, exc)
        raise SystemExit(1) from exc


def _payload(config: RemoteClientConfig) -> dict:
    inputs = [bool(config.command), bool(config.command_file), bool(config.python_file)]
    if sum(inputs) != 1:
        raise ValueError("Provide exactly one of --command, --command-file, or --python-file.")
    if config.python_file:
        path = Path(config.python_file)
        return {"timeout": config.timeout, "python_code": path.read_text("utf-8"), "display_name": str(path)}
    if config.command_file:
        return {"timeout": config.timeout, "command": Path(config.command_file).read_text("utf-8")}
    return {"timeout": config.timeout, "command": config.command}


@register("remote_client")
class RemoteClientFlow(BaseFlow[RemoteClientConfig]):
    """Flow that calls the remote execution server."""

    output_keys = ["result"]

    def build_steps(self) -> list:
        """Return the client action step."""
        return [self.run]

    def run(self) -> None:
        """Run the requested remote client action."""
        host = _host(self.config.host)
        port = self.config.port
        action = self.config.action

        if action == "ping":
            self.context["result"] = _get(host, port, "/ping")
        elif action == "tasks":
            self.context["result"] = _get(host, port, "/tasks", status=self.config.status, tail=self.config.tail)
        elif action == "kill":
            if not self.config.task_id:
                raise ValueError("--task-id is required for --action kill.")
            self.context["result"] = _post(host, port, f"/tasks/{self.config.task_id}/kill")
        elif action == "kill_all":
            self.context["result"] = _post(host, port, "/tasks/kill-all", timeout=60)
        else:
            stream_exec(host, port, _payload(self.config), self.config.timeout)
            self.context["result"] = "streamed"
