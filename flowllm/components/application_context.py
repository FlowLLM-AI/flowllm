"""Application context: shared state for components, jobs, and service."""

from typing import TYPE_CHECKING, Any

from ..enumeration import ComponentEnum
from ..schema import ApplicationConfig

if TYPE_CHECKING:
    from .base_component import BaseComponent
    from .job import BaseJob
    from .service import BaseService


class ApplicationContext:
    """Passive state container holding parsed config and wired components."""

    def __init__(self, **kwargs):
        self.app_config: ApplicationConfig = ApplicationConfig(**kwargs)
        self.service: "BaseService | None" = None
        self.components: dict[ComponentEnum, dict[str, "BaseComponent"]] = {}
        self.jobs: dict[str, "BaseJob"] = {}
        self.metadata: dict[str, Any] = {}
