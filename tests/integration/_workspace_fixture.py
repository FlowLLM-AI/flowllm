"""Shared fixture: temporary workspace environment for integration tests."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from typing import Any, Iterator


@contextlib.contextmanager
def temp_chdir(path) -> Iterator[Path]:
    """Temporarily chdir, restoring on exit."""
    old = os.getcwd()
    os.chdir(path)
    try:
        yield Path(path)
    finally:
        os.chdir(old)


class WorkspaceEnv:
    """Temp workspace + Application lifecycle helpers."""

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self._apps: list[Any] = []

    async def make_app(self, *, config: str | None = None, **overrides) -> Any:
        """Build, start, and track an Application for cleanup."""
        from flowllm import Application
        from flowllm.config import resolve_app_config

        kwargs: dict[str, Any] = {
            "log_to_console": False,
            "log_to_file": False,
            "enable_logo": False,
            "workspace_dir": str(self.workspace_dir),
        }
        if config:
            kwargs["config"] = config
        kwargs.update(overrides)
        cfg = resolve_app_config(**kwargs)
        app = Application(**cfg)
        await app.start()
        self._apps.append(app)
        return app

    async def close_all(self) -> None:
        """Close all tracked apps. Idempotent."""
        for app in self._apps:
            await app.close()
        self._apps.clear()

    def session_state_files(self, prefix: str = "session_state_") -> list[Path]:
        """List session-state JSONL files under session/."""
        session_dir = self.workspace_dir / "session"
        if not session_dir.exists():
            return []
        return sorted(session_dir.rglob(f"{prefix}*.jsonl"))


@contextlib.contextmanager
def workspace_env(
    *,
    chdir: bool = True,
    workspace_name: str = ".flowllm",
    load_env_file: bool = True,
) -> Iterator[WorkspaceEnv]:
    """Yield a fresh WorkspaceEnv in a temp directory."""
    if load_env_file:
        from flowllm.utils import load_env

        load_env()

    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir).resolve() / workspace_name
        workspace.mkdir(parents=True, exist_ok=True)
        env = WorkspaceEnv(workspace_dir=workspace)

        if chdir:
            with temp_chdir(workspace):
                yield env
        else:
            yield env
