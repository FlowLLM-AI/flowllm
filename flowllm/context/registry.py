from loguru import logger

from flowllm.context.base_context import BaseContext
from flowllm.utils.common_utils import camel_to_snake


class Registry(BaseContext):

    def __init__(self, registry_name: str, enable_log: bool = True, register_flow_module: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.registry_name: str = registry_name
        self.enable_log: bool = enable_log
        self.register_flow_module: bool = register_flow_module

    def register(self, name: str = ""):
        def decorator(cls):
            if not self.register_flow_module and cls.__module__.startswith("flowllm"):
                return cls

            class_name = name if name else camel_to_snake(cls.__name__)
            if self.enable_log:
                if class_name in self._data:
                    logger.warning(f"{self.registry_name}.class({class_name}) is already registered!")
                else:
                    logger.info(f"{self.registry_name}.class({class_name}) is registered.")

            self._data[class_name] = cls
            return cls

        return decorator
