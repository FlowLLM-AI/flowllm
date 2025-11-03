"""Asynchronous tool operation base class.

This module defines `BaseAsyncToolOp`, an abstract base operator that helps
implement asynchronous tool-like operations. It manages input/output schema
binding to a shared context, provides default result handling, and standardizes
pre/post execution hooks for derived ops.
"""

import json
from abc import ABCMeta
from typing import List

from loguru import logger

from .base_async_op import BaseAsyncOp
from ..schema import ToolCall, ParamAttrs


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
        save_answer: bool = False,
        input_schema_mapping: dict = None,
        output_schema_mapping: dict = None,
        **kwargs,
    ):
        """Initialize the async tool operator.

        Args:
            enable_print_output: Whether to log output dictionaries.
            tool_index: Index for disambiguating multiple instances of the tool.
            save_answer: If True, write primary output into `response.answer`.
            input_schema_mapping: Optional mapping from input names to context keys.
            output_schema_mapping: Optional mapping from output names to context keys.
            **kwargs: Extra arguments forwarded to `BaseAsyncOp`.
        """
        super().__init__(**kwargs)

        self.enable_print_output: bool = enable_print_output
        self.tool_index: int = tool_index
        self.save_answer: bool = save_answer
        self.input_schema_mapping: dict | None = input_schema_mapping  # map key to context
        self.output_schema_mapping: dict | None = output_schema_mapping  # map key to context

        self._tool_call: ToolCall | None = None
        self.input_dict: dict = {}  # Actual input values extracted from context
        self.output_dict: dict = {}  # Actual output values to save to context

    def build_tool_call(self) -> ToolCall:
        """Build and return the tool call schema for this operator.

        Subclasses should override to provide `description`, `input_schema`, and
        optionally `output_schema`. If `output_schema` is not provided, a default
        single string output will be created.
        """
        return ToolCall(**{"description": "", "input_schema": {}})

    @property
    def tool_call(self):
        """Return the lazily constructed `ToolCall` describing this tool."""
        if self._tool_call is None:
            self._tool_call = self.build_tool_call()
            self._tool_call.name = self.short_name
            self._tool_call.index = self.tool_index

            if not self._tool_call.output_schema:
                self._tool_call.output_schema = {
                    f"{self.short_name}_result": ParamAttrs(
                        type="str",
                        description=f"The execution result of the {self.short_name}",
                    ),
                }

        return self._tool_call

    @property
    def output_keys(self) -> str | List[str]:
        """Return the output key name or list of names defined by the schema."""
        output_keys = []
        for name, _ in self.tool_call.output_schema.items():
            if name not in output_keys:
                output_keys.append(name)

        if len(output_keys) == 1:
            return output_keys[0]
        else:
            return output_keys

    @property
    def output(self) -> str:
        """Convenience accessor for the primary output value.

        Raises:
            NotImplementedError: If multiple outputs exist; use `output_dict`.
        """
        if isinstance(self.output_keys, str):
            return self.output_dict[self.output_keys]
        else:
            raise NotImplementedError("use `output_dict` to get result")

    def set_result(self, value="", key: str = ""):
        """Set a single output value.

        If only one output key exists, `key` is ignored and the single key is
        used. Otherwise, `key` must be provided.
        """
        if isinstance(self.output_keys, str):
            self.output_dict[self.output_keys] = value
        else:
            self.output_dict[key] = value

    def set_results(self, **kwargs):
        """Set multiple output values using keyword arguments."""
        for k, v in kwargs.items():
            self.set_result(v, k)

    async def async_before_execute(self):
        """Populate `input_dict` by reading required inputs from the context.

        Applies `input_schema_mapping` and appends the `tool_index` suffix when
        necessary. Raises if any required input is missing.
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

        Applies `output_schema_mapping` and appends the `tool_index` suffix when
        necessary. Logs outputs when enabled.
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
            if self.tool_index == 0:
                logger.info(f"{self.name}.output_dict={self.output_dict}")
            else:
                logger.info(f"{self.name}.{self.tool_index}.output_dict={self.output_dict}")

    async def async_default_execute(self):
        """Fill outputs with a default failure message when execution fails."""
        if isinstance(self.output_keys, str):
            self.output_dict[self.output_keys] = f"{self.name} execution failed!"
        else:
            for output_key in self.output_keys:
                self.output_dict[output_key] = f"{self.name} execution failed!"
