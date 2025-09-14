import json
from abc import ABCMeta
from typing import List

from loguru import logger

from flowllm.op.base_async_op import BaseAsyncOp
from flowllm.schema.tool_call import ToolCall
from flowllm.storage.cache import DataCache


class BaseAsyncToolOp(BaseAsyncOp, metaclass=ABCMeta):

    def __init__(self,
                 enable_cache: bool = False,
                 cache_dir: str = "cache",
                 cache_expire_hours: float = 0.1,
                 enable_print_output: bool = True,
                 tool_index: int = 0,
                 save_answer: bool = False,
                 **kwargs):
        super().__init__(**kwargs)

        self.enable_cache: bool = enable_cache
        self.cache_dir: str = cache_dir
        self.cache_expire_hours: float = cache_expire_hours
        self.enable_print_output: bool = enable_print_output
        self.tool_index: int = tool_index
        self.save_answer: bool = save_answer

        self._cache: DataCache | None = None
        self._tool_call: ToolCall | None = None
        self.input_dict: dict = {}
        self.output_dict: dict = {}

    @property
    def cache(self):
        if self.enable_cache and self._cache is None:
            self._cache = DataCache(f"{self.cache_dir}/{self.name}")
        return self._cache

    def build_tool_call(self) -> ToolCall:
        ...

    @property
    def tool_call(self):
        if self._tool_call is None:
            self._tool_call = self.build_tool_call()
        return self._tool_call

    @property
    def output_keys(self) -> str | List[str]:
        output_keys = []
        for name, attrs in self.tool_call.output_schema.items():
            if name not in output_keys:
                output_keys.append(name)

        if len(output_keys) == 1:
            return output_keys[0]
        else:
            return output_keys

    @property
    def output(self) -> str | dict:
        if isinstance(self.output_keys, str):
            return self.output_dict[self.output_keys]
        else:
            return {k: self.output_dict[k] for k in self.output_keys if k in self.output_dict}

    def set_result(self, value: str = "", key: str = ""):
        if isinstance(self.output_keys, str):
            self.output_dict[self.output_keys] = value
        else:
            self.output_dict[key] = value

    def set_results(self, **kwargs):
        for k, v in kwargs.items():
            self.set_result(v, k)

    async def async_before_execute(self):
        for name, attrs in self.tool_call.input_schema.items():
            if name in self.context:
                self.input_dict[name] = self.context[name]
            elif attrs.required:
                raise ValueError(f"{name} is required")

    async def async_after_execute(self):
        if self.tool_index == 0:
            self.context.update(self.output_dict)
        else:
            self.context.update({f"{k}.{self.tool_index}": v for k, v in self.output_dict.items()})

        if self.save_answer:
            if isinstance(self.output_keys, str):
                self.context.response.answer = self.output_dict[self.output_keys]
            else:
                self.context.response.answer = json.dumps(self.output_dict, ensure_ascii=False)

        if self.enable_print_output:
            if self.tool_index == 0:
                logger.info(f"{self.name}.output_dict={self.output_dict}")
            else:
                logger.info(f"{self.name}.{self.tool_index}.output_dict={self.output_dict}")

    async def async_default_execute(self):
        if isinstance(self.output_keys, str):
            self.output_dict[self.output_keys] = f"{self.name} execution failed!"
        else:
            for output_key in self.output_keys:
                self.output_dict[output_key] = f"{self.name} execution failed!"
