"""Exit plan mode operation module.

This module provides a tool operation for exiting plan mode after presenting
an implementation plan to the user for approval.
"""

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class ExitPlanModeOp(BaseAsyncToolOp):
    """Exit plan mode operation.

    This operation is used when in plan mode and ready to present the plan
    to the user for approval before proceeding with implementation.
    """

    file_path = __file__

    def __init__(self, **kwargs):
        kwargs.setdefault("raise_exception", False)
        super().__init__(**kwargs)

    def build_tool_call(self) -> ToolCall:
        """Build and return the tool call schema for this operator."""
        tool_params = {
            "name": "ExitPlanMode",
            "description": self.get_prompt("tool_desc"),
            "input_schema": {
                "plan": {
                    "type": "string",
                    "description": self.get_prompt("plan"),
                    "required": True,
                },
            },
        }

        return ToolCall(**tool_params)

    async def async_execute(self):
        """Execute the exit plan mode operation."""
        plan: str = self.input_dict.get("plan", "").strip()

        if not plan:
            raise ValueError("The 'plan' parameter cannot be empty.")

        result_msg = (
            f"Plan presented for approval:\n\n{plan}\n\nWaiting for user confirmation to proceed with implementation."
        )
        self.set_output(result_msg)

    async def async_default_execute(self, e: Exception = None, **kwargs):
        """Fill outputs with a default failure message when execution fails."""
        plan: str = self.input_dict.get("plan", "").strip()
        error_msg = f'Failed to present plan "{plan[:50]}..."' if len(plan) > 50 else f'Failed to present plan "{plan}"'
        if e:
            error_msg += f": {str(e)}"
        self.set_output(error_msg)
