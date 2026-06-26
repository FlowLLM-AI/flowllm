"""HTTP service: exposes jobs as FastAPI endpoints (JSON or SSE)."""

import asyncio
import warnings
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .base_service import BaseService
from ..component_registry import R
from ..job import BaseJob, StreamJob
from ...constants import FLOWLLM_DEFAULT_HOST, FLOWLLM_DEFAULT_PORT
from ...schema import Request, Response
from ...utils import execute_stream_task

if TYPE_CHECKING:
    from ...application import Application

_WEBSOCKET_DEPRECATION_PATTERNS = (
    r".*websockets\.legacy is deprecated.*",
    r".*WebSocketServerProtocol is deprecated.*",
)


@R.register("http")
class HttpService(BaseService):
    """Map jobs to JSON POST endpoints; StreamJobs to SSE endpoints."""

    def __init__(self, host: str = FLOWLLM_DEFAULT_HOST, port: int = FLOWLLM_DEFAULT_PORT, **kwargs):
        super().__init__(**kwargs)
        self.host: str = host
        self.port: int = port

    def build_service(self, app: "Application") -> None:
        self.service = FastAPI(title=app.config.app_name, lifespan=self._lifespan(app, self.host, self.port))
        self.service.add_middleware(
            CORSMiddleware,  # type: ignore[arg-type]
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def add_job(self, job: BaseJob) -> bool:
        if isinstance(job, StreamJob):
            self._add_stream_job(job)
        else:
            self._add_json_job(job)
        return True

    def start_service(self, app: "Application") -> None:
        for pattern in _WEBSOCKET_DEPRECATION_PATTERNS:
            warnings.filterwarnings("ignore", category=DeprecationWarning, message=pattern)
        uvicorn.run(self.service, host=self.host, port=self.port, **self.kwargs)

    def _add_json_job(self, job: BaseJob) -> None:
        async def endpoint(request: Request) -> Response:
            return await job(**request.model_dump(exclude_none=True))

        self.service.post(f"/{job.name}", response_model=Response, description=job.description)(endpoint)

    def _add_stream_job(self, job: StreamJob) -> None:
        async def endpoint(request: Request) -> StreamingResponse:
            stream_queue: asyncio.Queue = asyncio.Queue()
            task = asyncio.create_task(job(stream_queue=stream_queue, **request.model_dump(exclude_none=True)))

            async def body() -> AsyncGenerator[bytes, None]:
                async for chunk in execute_stream_task(
                    stream_queue=stream_queue,
                    task=task,
                    task_name=job.name,
                    output_format="bytes",
                ):
                    assert isinstance(chunk, bytes)
                    yield chunk

            return StreamingResponse(body(), media_type="text/event-stream")

        self.service.post(f"/{job.name}")(endpoint)
