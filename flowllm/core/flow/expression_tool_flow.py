"""Flow that builds from expression content and exposes a tool-call schema."""

from .base_tool_flow import BaseToolFlow
from ..schema import FlowConfig, ToolCall
from ..utils import parse_flow_expression


class ExpressionToolFlow(BaseToolFlow):
    """Tool-enabled flow constructed from `FlowConfig.flow_content`.

    The flow forwards cache-related parameters from `FlowConfig` to `BaseFlow`,
    enabling non-streaming response caching when configured.
    """

    def __init__(self, flow_config: FlowConfig = None, **kwargs):
        """Initialize the flow with a `FlowConfig`.

        Args:
            flow_config: Configuration containing expression, metadata, and
                optional caching controls (`enable_cache`, `cache_path`,
                `cache_expire_hours`).
        """
        self.flow_config: FlowConfig = flow_config
        super().__init__(
            name=flow_config.name,
            stream=self.flow_config.stream,
            enable_cache=self.flow_config.enable_cache,
            cache_path=self.flow_config.cache_path,
            cache_expire_hours=self.flow_config.cache_expire_hours,
            **kwargs,
        )

    def build_flow(self):
        """Parse and return the operation tree from the config content."""
        return parse_flow_expression(self.flow_config.flow_content)

    def build_tool_call(self) -> ToolCall:
        """Construct and return the `ToolCall` for this flow.

        If the underlying op already defines a `tool_call`, reuse it; otherwise,
        create a `ToolCall` using the metadata from `FlowConfig`.
        """
        if hasattr(self.flow_op, "tool_call"):
            return self.flow_op.tool_call
        else:
            return ToolCall(
                name=self.flow_config.name,
                description=self.flow_config.description,
                input_schema=self.flow_config.input_schema,
            )
