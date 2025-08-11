from loguru import logger

from v2.context.base_context import BaseContext
from v2.utils.common_utils import camel_to_snake


class RegistryContext(BaseContext):

    def register(self, name: str = ""):
        def decorator(cls):
            class_name = name if name else camel_to_snake(cls.__name__)
            if class_name in self._data:
                logger.warning(f"class({class_name}) is already registered!")
            self._data[class_name] = cls
            return cls

        return decorator
