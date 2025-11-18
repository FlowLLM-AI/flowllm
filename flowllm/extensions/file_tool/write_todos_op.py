"""Write todos operation module.

This module provides a tool operation for managing todo lists.
It enables tracking subtasks with status (pending, in_progress, completed, cancelled).
"""

from typing import List

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall

TODO_STATUSES = ["pending", "in_progress", "completed", "cancelled"]


@C.register_op()
class WriteTodosOp(BaseAsyncToolOp):
    """Write todos operation.

    This operation manages a todo list with subtasks that can be tracked
    through different statuses: pending, in_progress, completed, cancelled.
    """

    file_path = __file__

    def __init__(self, **kwargs):
        kwargs.setdefault("raise_exception", False)
        super().__init__(**kwargs)

    def build_tool_call(self) -> ToolCall:
        """Build and return the tool call schema for this operator."""
        tool_params = {
            "name": "WriteTodos",
            "description": self.get_prompt("tool_desc"),
            "input_schema": {
                "todos": {
                    "type": "array",
                    "description": self.get_prompt("todos"),
                    "required": True,
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": self.get_prompt("todo_description"),
                            },
                            "status": {
                                "type": "string",
                                "description": self.get_prompt("todo_status"),
                                "enum": TODO_STATUSES,
                            },
                        },
                        "required": ["description", "status"],
                    },
                },
            },
        }

        return ToolCall(**tool_params)

    async def async_execute(self):
        """Execute the write todos operation."""
        todos: List[dict] = self.input_dict.get("todos", [])

        # Validate todos
        if not isinstance(todos, list):
            raise ValueError("The 'todos' parameter must be an array")

        # Validate each todo item
        for i, todo in enumerate(todos):
            if not isinstance(todo, dict):
                raise ValueError(f"Todo item at index {i} must be an object")

            if "description" not in todo or not isinstance(todo["description"], str):
                raise ValueError(f"Todo item at index {i} must have a non-empty description string")

            if not todo["description"].strip():
                raise ValueError(f"Todo item at index {i} must have a non-empty description string")

            if "status" not in todo or todo["status"] not in TODO_STATUSES:
                raise ValueError(
                    f"Todo item at index {i} must have a valid status ({', '.join(TODO_STATUSES)})",
                )

        # Validate only one in_progress task
        in_progress_count = sum(1 for todo in todos if todo.get("status") == "in_progress")
        if in_progress_count > 1:
            raise ValueError("Only one task can be 'in_progress' at a time")

        # Format todo list
        if not todos:
            result_message = "Successfully cleared the todo list."
        else:
            todo_list_string = "\n".join(
                f"{i + 1}. [{todo['status']}] {todo['description']}" for i, todo in enumerate(todos)
            )
            result_message = f"Successfully updated the todo list. The current list is now:\n{todo_list_string}"

        self.set_output(result_message)

    async def async_default_execute(self, e: Exception = None, **kwargs):
        """Fill outputs with a default failure message when execution fails."""
        error_msg = "Failed to update the todo list"
        if e:
            error_msg += f": {str(e)}"
        self.set_output(error_msg)
