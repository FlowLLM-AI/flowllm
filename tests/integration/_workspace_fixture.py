"""Shared integration-test fixture: build a workspace test environment.

    from _workspace_fixture import workspace_env

    async def run():
        with workspace_env() as env:
            app = await env.make_app()
            try:
                ...
            finally:
                await env.close_all()
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from typing import Any, Iterator


@contextlib.contextmanager
def temp_chdir(path) -> Iterator[Path]:
    """``chdir`` to ``path`` for the block; restore the original cwd on exit."""
    old = os.getcwd()
    os.chdir(path)
    try:
        yield Path(path)
    finally:
        os.chdir(old)


class WorkspaceEnv:
    """A workspace test environment — temp workspace + helpers."""

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self._apps: list[Any] = []

    async def make_app(self, *, config: str | None = None, **overrides) -> Any:
        """Build and start an ``Application`` and track it for cleanup."""
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
        """Close every app started via this env. Idempotent."""
        for app in self._apps:
            await app.close()
        self._apps.clear()

    def session_state_files(self, prefix: str = "session_state_") -> list[Path]:
        """All session-state jsonl files under ``resource/``."""
        resource_dir = self.workspace_dir / "resource"
        if not resource_dir.exists():
            return []
        return sorted(resource_dir.rglob(f"{prefix}*.jsonl"))


@contextlib.contextmanager
def workspace_env(
    *,
    chdir: bool = True,
    workspace_name: str = ".flowllm",
    load_env_file: bool = True,
) -> Iterator[WorkspaceEnv]:
    """Yield a fresh ``WorkspaceEnv`` rooted at a temp workspace."""
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
