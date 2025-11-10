"""Base class for flows exposing a tool-call interface.

Provides `tool_call` construction for flows intended to be surfaced as tools
to external orchestrators or agents.
"""

from abc import ABC

from .base_flow import BaseFlow
from ..schema import ToolCall


class BaseToolFlow(BaseFlow, ABC):
    """Abstract base flow that also exposes a `ToolCall` descriptor."""

    def __init__(self, **kwargs):
        """Initialize the tool flow."""
        super().__init__(**kwargs)
        self._tool_call: ToolCall | None = None

    def build_tool_call(self) -> ToolCall:
        """Build and return the `ToolCall` describing this flow."""

    @property
    def tool_call(self) -> ToolCall:
        """Lazily build and cache the exported `ToolCall`."""
        if self._tool_call is None:
            self._tool_call = self.build_tool_call()
        return self._tool_call
