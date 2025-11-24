"""Asynchronous tool operation base class.

This module defines `BaseAsyncToolOp`, an abstract base operator that helps
implement asynchronous tool-like operations. It manages input/output schema
binding to a shared context, provides default result handling, and standardizes
pre- / post-execution hooks for derived ops.
"""

import json
from abc import ABCMeta
from typing import List

from loguru import logger

from .base_async_op import BaseAsyncOp
from ..schema import ToolCall, ToolAttr


class BaseAsyncToolOp(BaseAsyncOp, metaclass=ABCMeta):
    """Base class for async tool operators.

    Subclasses describe their tool interface via `build_tool_call()` and
    implement their asynchronous execution while relying on this class to:
    - extract inputs from the context before execution
    - store outputs back into the context after execution
    - optionally save the primary output to the response answer
    - provide simple helpers for setting single or multiple results
    """

    def __init__(
        self,
        enable_print_output: bool = True,
        tool_index: int = 0,
        save_answer: bool = True,
        input_schema_mapping: dict = None,
        output_schema_mapping: dict = None,
        max_print_output_length: int = 200,
        **kwargs,
    ):
        """Initialize the async tool operator.

        Args:
            enable_print_output: Whether to log output dictionaries.
            tool_index: Index for disambiguating multiple instances of the tool.
            save_answer: If True, write primary output into `response.answer`.
            input_schema_mapping: Optional mapping from input names to context keys.
            output_schema_mapping: Optional mapping from output names to context keys.
            max_print_output_length: Maximum length of output strings to log.
            **kwargs: Extra arguments forwarded to `BaseAsyncOp`.
        """
        super().__init__(**kwargs)

        self.enable_print_output: bool = enable_print_output
        self.tool_index: int = tool_index
        self.save_answer: bool = save_answer
        self.input_schema_mapping: dict | None = input_schema_mapping  # map key to context
        self.output_schema_mapping: dict | None = output_schema_mapping  # map key to context
        self.max_print_output_length: int = max_print_output_length

        self._tool_call: ToolCall | None = None
        self.input_dict: dict = {}  # Actual input values extracted from context
        self.output_dict: dict = {}  # Actual output values to save to context

    def build_tool_call(self) -> ToolCall:
        """Build and return the tool call schema for this operator.

        Subclasses should override to provide `description`, `input_schema`, and
        optionally `output_schema`. If `output_schema` is not provided, a default
        single string output will be created.

        Returns:
            ToolCall instance describing the tool's interface

        Example:
            ```python
            def build_tool_call(self) -> ToolCall:
                return ToolCall(
                    **{
                        "description": "Search the web for information",
                        "input_schema": {
                            "query": {
                                "type": "string",
                                "description":"Search query",
                                "required": True,
                            },
                        },
                    }
                )
            ```
        """
        return ToolCall(**{"description": "", "input_schema": {}})

    @property
    def tool_call(self):
        """Return the lazily constructed `ToolCall` describing this tool.

        The tool call is constructed on first access by calling `build_tool_call()`.
        The name and index are automatically set from the operator's short_name
        and tool_index.

        Returns:
            ToolCall instance with name and index set
        """
        if self._tool_call is None:
            self._tool_call = self.build_tool_call()
            if not self._tool_call.name:
                self._tool_call.name = self.short_name

            if not self._tool_call.index:
                self._tool_call.index = self.tool_index

            if not self._tool_call.output_schema:
                self._tool_call.output_schema = {
                    f"{self.short_name}_result": ToolAttr(
                        type="string",
                        description=f"The execution result of the {self.short_name}",
                    ),
                }

        return self._tool_call

    @property
    def output_keys(self) -> str | List[str]:
        """Return the output key name or list of names defined by the schema.

        If the tool has a single output, returns the key name as a string.
        If the tool has multiple outputs, returns a list of key names.

        Returns:
            Single output key name (str) or list of output key names (List[str])
        """
        output_keys = []
        for name, _ in self.tool_call.output_schema.items():
            if name not in output_keys:
                output_keys.append(name)

        if len(output_keys) == 1:
            return output_keys[0]
        else:
            return output_keys

    @property
    def output(self):
        """Convenience accessor for the primary output value.

        Raises:
            NotImplementedError: If multiple outputs exist; use `output_dict`.
        """
        if isinstance(self.output_keys, str):
            return self.output_dict[self.output_keys]
        else:
            raise NotImplementedError("use `output_dict` to get result")

    def set_output(self, value="", key: str = ""):
        """Set a single output value.

        If only one output key exists, `key` is ignored and the single key is
        used. Otherwise, `key` must be provided.

        Args:
            value: The output value to set
            key: The output key name (required if multiple outputs exist)

        Raises:
            KeyError: If multiple outputs exist and `key` is not provided or
                doesn't match any output key
        """
        if isinstance(self.output_keys, str):
            self.output_dict[self.output_keys] = value
        else:
            self.output_dict[key] = value

    def set_outputs(self, **kwargs):
        """Set multiple output values using keyword arguments.

        Args:
            **kwargs: Keyword arguments where keys are output names and values
                are the output values

        Example:
            ```python
            self.set_outputs(result="success", count=10, status="ok")
            ```
        """
        for k, v in kwargs.items():
            self.set_output(v, k)

    async def async_before_execute(self):
        """Populate `input_dict` by reading required inputs from the context.

        Applies `input_schema_mapping` and appends the `tool_index` suffix when
        necessary. Raises if any required input is missing.

        Raises:
            ValueError: If any required input is missing from the context
        """
        for name, attrs in self.tool_call.input_schema.items():
            context_key = name
            if self.input_schema_mapping and name in self.input_schema_mapping:
                context_key = self.input_schema_mapping[name]
            if self.tool_index != 0:
                context_key += f".{self.tool_index}"

            if context_key in self.context:
                self.input_dict[name] = self.context[context_key]
            elif attrs.required:
                raise ValueError(f"{self.name}: {name} is required")

    async def async_after_execute(self):
        """Write `output_dict` back to the context and optionally save answer.

        This method:
        1. Writes all values from `output_dict` to the context using the
           appropriate keys (with mapping and index suffix if needed)
        2. Optionally saves the primary output to `context.response.answer`
           if `save_answer` is True
        3. Logs the output dictionary if `enable_print_output` is True

        Applies `output_schema_mapping` and appends the `tool_index` suffix when
        necessary.
        """
        for name, value in self.output_dict.items():
            context_key = name
            if self.output_schema_mapping and name in self.output_schema_mapping:
                context_key = self.output_schema_mapping[name]
            if self.tool_index != 0:
                context_key += f".{self.tool_index}"

            logger.info(f"{self.name} set context key={context_key}")
            self.context[context_key] = value

        if self.save_answer:
            if isinstance(self.output_keys, str):
                self.context.response.answer = self.output_dict.get(self.output_keys, "")
            else:
                self.context.response.answer = json.dumps(self.output_dict, ensure_ascii=False)

        if self.enable_print_output:
            output_str = str(self.output_dict)
            if len(output_str) > self.max_print_output_length:
                output_str = f"{output_str[:self.max_print_output_length]}..."

            if self.tool_index == 0:
                logger.info(f"{self.name}.output_dict={output_str}")
            else:
                logger.info(f"{self.name}.{self.tool_index}.output_dict={output_str}")

    async def async_default_execute(self, e: Exception = None, **kwargs):
        """Fill outputs with a default failure message when execution fails.

        This method is called when `async_execute()` fails. It sets all output
        keys in `output_dict` to a failure message string.

        Args:
            e: The exception that was raised during execution (if any)
            **kwargs: Additional keyword arguments (not used by default)
        """
        if isinstance(self.output_keys, str):
            self.output_dict[self.output_keys] = f"{self.name} execution failed!"
        else:
            for output_key in self.output_keys:
                self.output_dict[output_key] = f"{self.name} execution failed!"
