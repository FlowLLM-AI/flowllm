"""Base agent wrapper component."""

from abc import abstractmethod
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel

from ..base_component import BaseComponent
from ...enumeration import ChunkEnum, ComponentEnum
from ...schema import StreamChunk

if TYPE_CHECKING:
    from ..job.base_job import BaseJob


class BaseAgentWrapper(BaseComponent):
    """Abstract base for agent wrappers with swappable backends."""

    component_type = ComponentEnum.AGENT_WRAPPER

    def set_system_prompt(self, prompt: str) -> "BaseAgentWrapper":
        """Set the system prompt."""
        self.kwargs["system_prompt"] = prompt
        return self

    def add_job_tools(self, job_tools: list[str]) -> "BaseAgentWrapper":
        """Append job tools by name."""
        self.kwargs.setdefault("job_tools", []).extend(job_tools)
        return self

    def add_skills(self, skills: list[str] | str) -> "BaseAgentWrapper":
        """Set skills configuration."""
        self.kwargs["skills"] = skills
        return self

    @property
    def project_path(self) -> Path:
        """Root path of the project."""
        return self.workspace_path

    @property
    def project_skills_root(self) -> Path:
        """Skills directory under project root."""
        return self.project_path / "skills"

    def set_output_schema(self, schema: dict | type[BaseModel]) -> "BaseAgentWrapper":
        """Set structured output schema."""
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            schema = schema.model_json_schema()
        self.kwargs["output_schema"] = schema
        return self

    def _resolve_job_tools(self, job_tools: list[str]) -> list["BaseJob"]:
        if not job_tools:
            return []
        if self.app_context is None:
            raise RuntimeError("Cannot resolve job_tools without an app_context")
        resolved: list["BaseJob"] = []
        for name in job_tools:
            if (job := self.app_context.jobs.get(name)) is None:
                raise KeyError(f"Job '{name}' not found in app_context.jobs")
            resolved.append(job)
        return resolved

    def _merged_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        return {**self.kwargs, **kwargs}

    @staticmethod
    def _chunk(chunk_type: ChunkEnum = ChunkEnum.CONTENT, **kwargs: Any) -> StreamChunk:
        return StreamChunk(chunk_type=chunk_type, **kwargs)

    @abstractmethod
    async def reply(self, inputs: Any, **kwargs) -> dict:
        """Send inputs and return dict with session_id and last_message."""

    async def reply_stream(self, inputs: Any, **kwargs) -> AsyncGenerator[StreamChunk, None]:
        """Stream agent events as StreamChunk objects."""
