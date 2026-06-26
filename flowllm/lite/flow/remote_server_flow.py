"""Remote command execution server flow for ``fl --remote-server``."""

import asyncio
import os
import signal
import sys
import tempfile
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from ..cli import BaseConfig, BaseFlow, register

PROJECT_DIR = Path(os.environ.get("FLOWLLM_REMOTE_PROJECT_DIR", Path.cwd())).resolve()
SERVER_PID = os.getpid()

app = FastAPI(title="FlowLLM Lite Remote Executor")
_config: "RemoteServerConfig | None" = None


def config() -> "RemoteServerConfig":
    """Return the active server config or its defaults."""
    if _config is None:
        return RemoteServerConfig()
    return _config


@dataclass
class TaskInfo:
    """Runtime state for a remote execution task."""

    task_id: int
    command: str
    pid: int
    start_time: float
    status: str = "running"
    returncode: int | None = None
    output: deque[str] = field(default_factory=deque)
    proc: asyncio.subprocess.Process | None = field(default=None, repr=False)


class ExecRequest(BaseModel):
    """Request body for command or Python-code execution."""

    command: str | None = None
    python_code: str | None = None
    display_name: str | None = None
    timeout: int = 3600


class RemoteServerConfig(BaseConfig):
    """Configuration for the remote execution server."""

    host: str = "0.0.0.0"
    port: int = 8765
    timeout: int = 3600
    max_output_lines: int = 500
    max_finished_tasks: int = 100
    finished_task_ttl: int = 3600
    kill_grace_seconds: int = 5


_task_counter = 0
_tasks: dict[int, TaskInfo] = {}


def _register(command: str, proc: asyncio.subprocess.Process) -> TaskInfo:
    global _task_counter
    _task_counter += 1
    _tasks[_task_counter] = TaskInfo(_task_counter, command, proc.pid, time.time(), proc=proc)
    _tasks[_task_counter].output = deque(maxlen=config().max_output_lines)
    return _tasks[_task_counter]


def _finish(info: TaskInfo, returncode: int | None, status: str = "finished") -> None:
    info.status, info.returncode, info.proc = status, returncode, None
    _cleanup()


def _cleanup() -> None:
    cfg = config()
    now = time.time()
    for tid, task in list(_tasks.items()):
        if task.status in ("finished", "killed") and now - task.start_time > cfg.finished_task_ttl:
            del _tasks[tid]
    done = sorted((x for x in _tasks.items() if x[1].status in ("finished", "killed")), key=lambda x: x[1].start_time)
    for tid, _ in done[: -cfg.max_finished_tasks]:
        del _tasks[tid]


def _reap() -> None:
    for info in list(_tasks.values()):
        if info.status != "running":
            continue
        if info.proc is not None and info.proc.returncode is not None:
            _finish(info, info.proc.returncode)
            continue
        try:
            os.kill(info.pid, 0)
        except ProcessLookupError:
            _finish(info, -1)


async def _kill(proc: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    for _ in range(config().kill_grace_seconds * 10):
        if proc.returncode is not None:
            return
        await asyncio.sleep(0.1)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    await proc.wait()


@app.get("/ping")
async def ping():
    """Return server health and process metadata."""
    return {"status": "ok", "project_dir": str(PROJECT_DIR), "pid": SERVER_PID}


@app.get("/tasks")
async def list_tasks(status: str | None = None, tail: int = 30):
    """List tracked tasks, optionally filtered by status."""
    _reap()
    return [
        {
            "task_id": x.task_id,
            "command": x.command,
            "pid": x.pid,
            "status": x.status,
            "returncode": x.returncode,
            "elapsed": round(time.time() - x.start_time, 1),
            "output_tail": list(x.output)[-tail:],
        }
        for x in _tasks.values()
        if not status or x.status == status
    ]


@app.post("/tasks/{task_id}/kill")
async def kill_task(task_id: int):
    """Terminate a running task by id."""
    info = _tasks.get(task_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    if info.status != "running" or info.proc is None:
        return {"task_id": task_id, "status": info.status, "message": "already finished"}
    await _kill(info.proc)
    _finish(info, info.proc.returncode, "killed")
    return {"task_id": task_id, "status": "killed"}


@app.post("/tasks/kill-all")
async def kill_all_tasks():
    """Terminate all currently running tasks."""
    _reap()
    results = []
    running = [(tid, task) for tid, task in _tasks.items() if task.status == "running" and task.proc is not None]
    for tid, info in running:
        try:
            await _kill(info.proc)
            _finish(info, info.proc.returncode, "killed")
            results.append({"task_id": tid, "status": "killed"})
        except Exception as e:
            logger.exception("kill task {} failed", tid)
            results.append({"task_id": tid, "status": "error", "detail": str(e)})
    return {"killed": len([x for x in results if x["status"] == "killed"]), "tasks": results}


async def _start(req: ExecRequest):
    """Start the subprocess for an execution request."""
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    if req.python_code is None:
        assert req.command is not None
        return (
            None,
            req.command,
            await asyncio.create_subprocess_shell(
                req.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(PROJECT_DIR),
                env=env,
                start_new_session=True,
                limit=4 * 1024 * 1024,
            ),
        )
    env["PYTHONPATH"] = str(PROJECT_DIR) if not env.get("PYTHONPATH") else f"{PROJECT_DIR}:{env['PYTHONPATH']}"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".py", prefix="flowllm_remote_", delete=False) as tmp:
        tmp.write(req.python_code)
    return (
        tmp.name,
        f"python {req.display_name or '<uploaded-code>'}",
        await asyncio.create_subprocess_exec(
            sys.executable,
            tmp.name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(PROJECT_DIR),
            env=env,
            start_new_session=True,
            limit=4 * 1024 * 1024,
        ),
    )


@app.post("/exec")
async def exec_command(req: ExecRequest):
    """Execute a command or uploaded Python code and stream output."""
    if bool(req.command) == bool(req.python_code):
        raise HTTPException(status_code=400, detail="provide exactly one of command or python_code")
    if req.timeout == ExecRequest.model_fields["timeout"].default:
        req.timeout = config().timeout
    tmp, label, proc = await _start(req)
    info = _register(label, proc)

    async def _stream():
        try:
            assert proc.stdout is not None
            deadline = time.monotonic() + req.timeout
            while True:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=max(deadline - time.monotonic(), 0))
                if not line:
                    break
                info.output.append(line.decode(errors="replace").rstrip("\n"))
                yield line
            await asyncio.wait_for(proc.wait(), timeout=max(deadline - time.monotonic(), 0))
        except asyncio.TimeoutError:
            await _kill(proc)
            _finish(info, proc.returncode)
            yield b"\n[TIMEOUT]\n"
            return
        except asyncio.CancelledError:
            await _kill(proc)
            _finish(info, proc.returncode)
            return
        finally:
            if tmp:
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass
        _finish(info, proc.returncode)
        yield f"\n[EXIT:{proc.returncode}]\n".encode()

    return StreamingResponse(_stream(), media_type="text/plain")


@register("remote_server")
class RemoteServerFlow(BaseFlow[RemoteServerConfig]):
    """Flow that starts the remote execution server."""

    output_keys = ["result"]

    def build_steps(self) -> list:
        """Return the server startup step."""
        return [self.run_server]

    def run_server(self) -> None:
        """Run the FastAPI server."""
        import uvicorn

        global _config
        _config = self.config
        logger.info("Project dir : {}", PROJECT_DIR)
        logger.info("Server PID  : {}", SERVER_PID)
        logger.info("Listening on: {}:{}", self.config.host, self.config.port)
        uvicorn.run(app, host=self.config.host, port=self.config.port)
        self.context["result"] = "stopped"
