import json
from abc import ABCMeta
from typing import List

from loguru import logger

from flowllm.op.base_async_op import BaseAsyncOp
from flowllm.schema.tool_call import ToolCall, ParamAttrs


class BaseAsyncToolOp(BaseAsyncOp, metaclass=ABCMeta):
    """
    Base class for async tool operations with schema-based input/output handling.

    Extends BaseAsyncOp to provide:
    - Tool schema definition (input/output parameters with types and descriptions)
    - Automatic context mapping for input/output parameters
    - Support for multiple tool instances via tool_index
    - Result formatting and storage

    Tool operations are the bridge between LLM function calls and actual implementations.
    They define what parameters a tool needs and what it returns.
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
        """
        Initialize a tool operation.

        Args:
            enable_print_output: Whether to log output dict
            tool_index: Index for multiple instances of same tool (0=default, >0 for copies)
            save_answer: Whether to save output to context.response.answer
            input_schema_mapping: Map input parameter names to different context keys
            output_schema_mapping: Map output parameter names to different context keys
            **kwargs: Additional parameters passed to BaseAsyncOp
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
        """
        Build the tool schema definition. Override this method to define your tool.

        Returns:
            ToolCall with description, input_schema, and optionally output_schema
        """
        return ToolCall(
            **{
                "description": "",
                "input_schema": {},
            },
        )

    @property
    def tool_call(self):
        """
        Get or initialize the tool call schema.

        Lazy initialization that:
        1. Calls build_tool_call() to get the schema
        2. Sets name and index
        3. Adds default output_schema if not provided

        Returns:
            ToolCall instance with complete schema
        """
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
        """
        Get the output parameter name(s) from the tool schema.

        Returns:
            Single string if one output parameter, list of strings if multiple
        """
        output_keys = []
        for name, attrs in self.tool_call.output_schema.items():
            if name not in output_keys:
                output_keys.append(name)

        if len(output_keys) == 1:
            return output_keys[0]
        else:
            return output_keys

    @property
    def output(self) -> str:
        """
        Get the single output value (only works for single-output tools).

        Returns:
            Output value as string

        Raises:
            NotImplementedError: If tool has multiple outputs
        """
        if isinstance(self.output_keys, str):
            return self.output_dict[self.output_keys]
        else:
            raise NotImplementedError("use `output_dict` to get result")

    def set_result(self, value="", key: str = ""):
        """
        Set a single output value in output_dict.

        Args:
            value: Value to store
            key: Output parameter name (required for multi-output tools)
        """
        if isinstance(self.output_keys, str):
            self.output_dict[self.output_keys] = value
        else:
            self.output_dict[key] = value

    def set_results(self, **kwargs):
        """
        Set multiple output values at once.

        Args:
            **kwargs: key=value pairs for output parameters
        """
        for k, v in kwargs.items():
            self.set_result(v, k)

    async def async_before_execute(self):
        """
        Extract input parameters from context based on tool schema.

        For each input parameter in the schema:
        1. Determines context key (with optional mapping and tool_index suffix)
        2. Extracts value from context
        3. Validates required parameters
        4. Stores in input_dict for use in async_execute()

        Raises:
            ValueError: If a required parameter is missing from context
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
        """
        Store output parameters to context and optionally save to answer.

        For each output parameter:
        1. Determines context key (with optional mapping and tool_index suffix)
        2. Saves value to context for downstream operations
        3. Optionally saves to context.response.answer if save_answer=True
        4. Logs output if enable_print_output=True
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
        """
        Fallback behavior when tool execution fails.

        Sets all output parameters to error messages indicating failure.
        """
        if isinstance(self.output_keys, str):
            self.output_dict[self.output_keys] = f"{self.name} execution failed!"
        else:
            for output_key in self.output_keys:
                self.output_dict[output_key] = f"{self.name} execution failed!"
