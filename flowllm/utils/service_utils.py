"""Service discovery utilities."""

import asyncio
import socket
import subprocess
import sys

from ..constants import FLOWLLM_DEFAULT_HOST, FLOWLLM_DEFAULT_PORT


async def find_flowllm(host: str, port: int) -> str:
    """Probe host:port. Returns 'flowllm', 'occupied', or 'free'."""
    from ..components.client.http_client import HttpClient

    try:
        async with HttpClient(host=host, port=port, timeout=2.0) as client:
            async for _ in client(action="health_check"):
                break
        return "flowllm"
    except Exception:
        pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return "free"
        except OSError:
            return "occupied"


def _sh(cmd: list[str]) -> str:
    """Run cmd; return stdout, or '' on failure."""
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _pid_on_port(port: int) -> int | None:
    """PID listening on TCP port, or None."""
    out = _sh(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"]).strip()
    return int(out.splitlines()[0]) if out else None


def _scan_flowllm_procs() -> list[tuple[int, str, int]]:
    """List running flowllm start processes."""
    procs: list[tuple[int, str, int]] = []
    for line in _sh(["pgrep", "-af", "flowllm.* start"]).splitlines():
        parts = line.split()
        if not parts or not parts[0].isdigit():
            continue
        host, port = FLOWLLM_DEFAULT_HOST, FLOWLLM_DEFAULT_PORT
        for t in parts[1:]:
            if t.startswith("service.host="):
                host = t.split("=", 1)[1]
            elif t.startswith("service.port=") and t.split("=", 1)[1].isdigit():
                port = int(t.split("=", 1)[1])
        procs.append((int(parts[0]), host, port))
    return procs


async def _locate_flowllm() -> tuple[str, int, int | None] | None:
    """Find a running flowllm instance."""
    if await find_flowllm(FLOWLLM_DEFAULT_HOST, FLOWLLM_DEFAULT_PORT) == "flowllm":
        return FLOWLLM_DEFAULT_HOST, FLOWLLM_DEFAULT_PORT, _pid_on_port(FLOWLLM_DEFAULT_PORT)
    for pid, host, port in _scan_flowllm_procs():
        if await find_flowllm(host, port) == "flowllm":
            return host, port, pid
    return None


def precheck_start(svc_config: dict | None) -> bool:
    """Pre-flight check before starting."""
    host = (svc_config or {}).get("host") or FLOWLLM_DEFAULT_HOST
    port = (svc_config or {}).get("port") or FLOWLLM_DEFAULT_PORT
    port = int(port)
    status = asyncio.run(find_flowllm(host, port))
    if status == "flowllm":
        print(f"flowllm already running at {host}:{port}")
        return False
    if status == "occupied":
        print(
            f"port {port} occupied. Start on another port: flowllm start service.port=<other_port>",
            file=sys.stderr,
        )
        sys.exit(1)
    return True


def cli_find_flowllm() -> None:
    """Print running flowllm HOST/PORT/PID."""
    found = asyncio.run(_locate_flowllm())
    if not found:
        print("flowllm not started. Try: flowllm start", file=sys.stderr)
        sys.exit(1)
    host, port, pid = found
    print(f"HOST={host} PORT={port} PID={pid or 'unknown'}")
