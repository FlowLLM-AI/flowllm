"""Base client abstraction."""

import json
from abc import abstractmethod
from collections.abc import AsyncGenerator

from ..base_component import BaseComponent
from ...enumeration import ComponentEnum


class BaseClient(BaseComponent):
    """Abstract base for clients communicating with FlowLLM services."""

    component_type = ComponentEnum.CLIENT

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = None

    async def _start(self) -> None:
        pass

    async def _close(self) -> None:
        pass

    @abstractmethod
    def _execute(self, action: str, payload: dict) -> AsyncGenerator[str, None]:
        """Yield text chunks for action."""

    @abstractmethod
    async def list_actions(self) -> list[dict]:
        """Discover available actions."""

    async def __call__(self, action: str, **kwargs) -> AsyncGenerator[str, None]:
        if action == "list":
            yield json.dumps(await self.list_actions(), indent=2, ensure_ascii=False)
            return
        async for chunk in self._execute(action, kwargs):
            yield chunk
