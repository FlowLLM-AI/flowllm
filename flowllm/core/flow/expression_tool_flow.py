"""Flow that builds from expression content and exposes a tool-call schema."""

from .base_tool_flow import BaseToolFlow
from .expression_parser import ExpressionParser
from ..schema import FlowConfig, ToolCall


class ExpressionToolFlow(BaseToolFlow):
    """Tool-enabled flow constructed from `FlowConfig.flow_content`."""

    def __init__(self, flow_config: FlowConfig = None, **kwargs):
        """Initialize the flow with a `FlowConfig`.

        Args:
            flow_config: Configuration containing expression and metadata.
        """
        self.flow_config: FlowConfig = flow_config
        super().__init__(name=flow_config.name, stream=self.flow_config.stream, **kwargs)

    def build_flow(self):
        """Parse and return the operation tree from the config content."""
        parser = ExpressionParser(self.flow_config.flow_content)
        return parser.parse_flow()

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
