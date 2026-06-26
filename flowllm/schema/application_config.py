"""Application configuration schema."""

import os

from pydantic import BaseModel, ConfigDict, Field

from ..enumeration import ComponentEnum


class ComponentConfig(BaseModel):
    """Base component config with extra fields for backend-specific options."""

    model_config = ConfigDict(extra="allow")

    backend: str = Field(default="", description="Backend implementation class name")


class JobConfig(ComponentConfig):
    """Config for a job: an ordered sequence of steps."""

    description: str = Field(default="", description="Human-readable description")
    parameters: dict = Field(default_factory=dict, description="Job-level parameters")
    steps: list[ComponentConfig] = Field(default_factory=list, description="Ordered step configs")
    enable_serve: bool = Field(default=True, description="Whether to expose this job through the service layer")


class ApplicationConfig(BaseModel):
    """Root application config."""

    app_name: str = Field(default=os.getenv("APP_NAME", "FlowLLM"), description="Application display name")
    workspace_dir: str = Field(default=".flowllm", description="Workspace root directory for runtime files")
    metadata_dir: str = Field(default="metadata", description="Subdirectory for FlowLLM persistent state")
    session_dir: str = Field(default="session", description="Subdirectory for persisted agent sessions")
    enable_logo: bool = Field(default=True, description="Show ASCII logo on startup")
    timezone: str | None = Field(default="Asia/Shanghai", description="IANA timezone; None uses local time")
    language: str = Field(default="", description="Default language for LLM interactions")
    log_to_console: bool = Field(default=True, description="Log to console")
    log_to_file: bool = Field(default=True, description="Log to file")
    mcp_servers: dict[str, dict] = Field(default_factory=dict, description="MCP server configs by name")
    service: ComponentConfig = Field(default_factory=ComponentConfig, description="Service endpoint config")
    jobs: dict[str, JobConfig] = Field(default_factory=dict, description="Job definitions keyed by job name")
    components: dict[ComponentEnum, dict[str, ComponentConfig]] = Field(
        default_factory=dict,
        description="Component registry keyed by type then name",
    )
