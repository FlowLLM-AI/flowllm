"""Flow implementation that parses a string expression at runtime."""

from .base_flow import BaseFlow
from ..utils import parse_flow_expression


class CmdFlow(BaseFlow):
    """Build a flow from a user-provided expression string."""

    def __init__(self, flow: str = "", **kwargs):
        """Initialize with a flow expression.

        Args:
            flow: Expression to parse into a composed `BaseOp`.
        """
        super().__init__(**kwargs)
        self.flow = flow
        assert flow, "add `flow=<op_flow>` in cmd!"

    def build_flow(self):
        """Parse and return the operation built from the expression."""
        return parse_flow_expression(self.flow)
