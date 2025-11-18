"""Task delegation operation module.

This module provides a tool operation for delegating tasks to specialized subagents.
It enables primary agents to delegate complex, multi-step tasks to specialized agents.
"""

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class TaskOp(BaseAsyncToolOp):
    """Task delegation operation.

    This operation delegates tasks to specialized subagents for autonomous execution.
    """

    file_path = __file__

    def __init__(self, **kwargs):
        kwargs.setdefault("raise_exception", False)
        super().__init__(**kwargs)

    def build_tool_call(self) -> ToolCall:
        """Build and return the tool call schema for this operator."""
        tool_params = {
            "name": "Task",
            "description": self.get_prompt("tool_desc"),
            "input_schema": {
                "description": {
                    "type": "string",
                    "description": self.get_prompt("description"),
                    "required": True,
                },
                "prompt": {
                    "type": "string",
                    "description": self.get_prompt("prompt"),
                    "required": True,
                },
                "subagent_type": {
                    "type": "string",
                    "description": self.get_prompt("subagent_type"),
                    "required": True,
                },
            },
        }

        return ToolCall(**tool_params)

    async def async_execute(self):
        """Execute the task delegation operation."""
        description: str = self.input_dict.get("description", "").strip()
        prompt: str = self.input_dict.get("prompt", "").strip()
        subagent_type: str = self.input_dict.get("subagent_type", "").strip()

        # Validate parameters
        if not description:
            raise ValueError("The 'description' parameter cannot be empty.")

        if not prompt:
            raise ValueError("The 'prompt' parameter cannot be empty.")

        if not subagent_type:
            raise ValueError("The 'subagent_type' parameter cannot be empty.")

        # TODO: Implement actual subagent delegation logic
        # This is a placeholder implementation that needs to be integrated
        # with the actual subagent system when available
        result = (
            f"Task delegated to {subagent_type} subagent: {description}\n\n"
            f"Task prompt: {prompt}\n\n[Subagent execution result would appear here]"
        )

        self.set_output(result)

    async def async_default_execute(self, e: Exception = None, **kwargs):
        """Fill outputs with a default failure message when execution fails."""
        description: str = self.input_dict.get("description", "").strip()
        subagent_type: str = self.input_dict.get("subagent_type", "").strip()
        error_msg = f'Failed to delegate task "{description}" to subagent "{subagent_type}"'
        if e:
            error_msg += f": {str(e)}"
        self.set_output(error_msg)
