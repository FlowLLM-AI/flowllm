"""MCP service: expose jobs as MCP tools."""

from typing import TYPE_CHECKING

from fastmcp import FastMCP
from fastmcp.server.server import Transport
from fastmcp.tools import FunctionTool

from .base_service import BaseService
from ..component_registry import R
from ..job import BaseJob, StreamJob
from ...constants import FLOWLLM_DEFAULT_HOST, FLOWLLM_DEFAULT_PORT

if TYPE_CHECKING:
    from ...application import Application


@R.register("mcp")
class MCPService(BaseService):
    """Expose non-stream jobs as MCP tools over stdio, SSE, or streamable-http."""

    def __init__(
        self,
        transport: Transport = "sse",
        host: str = FLOWLLM_DEFAULT_HOST,
        port: int = FLOWLLM_DEFAULT_PORT,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.transport: Transport = transport
        self.host: str = host
        self.port: int = port

    def build_service(self, app: "Application") -> None:
        self.service = FastMCP(name=app.config.app_name, lifespan=self._lifespan(app, self.host, self.port))

    def add_job(self, job: BaseJob) -> bool:
        if isinstance(job, StreamJob):
            return False

        async def execute_tool(**kwargs):
            return (await job(**kwargs)).answer

        self.service.add_tool(
            FunctionTool(
                name=job.name,
                description=job.description,
                fn=execute_tool,
                parameters=job.parameters or {},
            ),
        )
        return True

    def start_service(self, app: "Application") -> None:
        transport_kwargs: dict = {}
        if self.transport != "stdio":
            transport_kwargs.update(host=self.host, port=self.port)
        self.service.run(transport=self.transport, show_banner=False, **transport_kwargs)
