from abc import ABC, abstractmethod

from loguru import logger

from flowllm.op.base_llm_op import BaseLLMOp
from flowllm.schema.tool_call import ToolCall
from flowllm.storage.cache import DataCache


class BaseToolOp(BaseLLMOp, ABC):

    def __init__(self,
                 enable_cache: bool = False,
                 cache_path: str = "cache",
                 cache_expire_hours: float = 0.1,
                 enable_print_output: bool = True,
                 **kwargs):
        super().__init__(**kwargs)

        self.enable_cache = enable_cache
        self.cache_path: str = cache_path
        self.cache_expire_hours: float = cache_expire_hours
        self.enable_print_output: bool = enable_print_output
        self._cache: DataCache | None = None

        self.tool_call: ToolCall = self.build_tool_call()
        self.input_dict: dict = {}
        self.output_dict: dict = {}

    @property
    def cache(self):
        if self.enable_cache and self._cache is None:
            self._cache = DataCache(f"{self.cache_path}/{self.name}")
        return self._cache

    @abstractmethod
    def build_tool_call(self) -> ToolCall:
        ...

    def before_execute(self):
        for key in self.tool_call.input_schema.keys():
            self.input_dict[key] = self.context.get(key)

    def after_execute(self):
        self.context.update(self.output_dict)
        if self.enable_print_output:
            logger.info(f"{self.name}.output_dict={self.output_dict}")
