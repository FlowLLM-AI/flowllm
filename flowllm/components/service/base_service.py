"""Base class for services that expose jobs over a network protocol."""

import json
import os
from abc import abstractmethod
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from ..base_component import BaseComponent
from ..job.base_job import BaseJob
from ...constants import FLOWLLM_SERVICE_INFO
from ...enumeration import ComponentEnum

if TYPE_CHECKING:
    from ...application import Application


class BaseService(BaseComponent):
    """Skeleton for services (HTTP, MCP, ...) that turn jobs into endpoints."""

    component_type = ComponentEnum.SERVICE

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = None

    @abstractmethod
    def build_service(self, app: "Application") -> None:
        """Build the underlying service instance."""

    @abstractmethod
    def add_job(self, job: BaseJob) -> bool:
        """Register a job; return True if exposed, False if skipped."""

    @abstractmethod
    def start_service(self, app: "Application") -> None:
        """Start the service and begin serving."""

    def _lifespan(self, app: "Application", host: str, port: int):
        """Async lifespan bracketing server with app start/close."""

        @asynccontextmanager
        async def lifespan(_):
            await app.start()
            service_info = json.dumps({"host": host, "port": port})
            os.environ[FLOWLLM_SERVICE_INFO] = service_info
            self.logger.info(f"{self.name} started: {FLOWLLM_SERVICE_INFO}={service_info}")
            yield
            await app.close()

        return lifespan

    def add_jobs(self, app: "Application") -> None:
        """Register all servable jobs from the app."""
        for name, job in app.context.jobs.items():
            if not job.enable_serve:
                continue
            try:
                if self.add_job(job):
                    self.logger.info(f"Added job: {name}")
                else:
                    self.logger.warning(f"Skipped job: {name}")
            except Exception as e:
                self.logger.error(f"Failed to add job {name}: {e}")

    def run_app(self, app: "Application") -> None:
        """Build, register jobs, and start the service."""
        self.build_service(app)
        self.add_jobs(app)
        self.start_service(app)
