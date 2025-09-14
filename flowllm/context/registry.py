from flowllm.context.base_context import BaseContext
from flowllm.utils.common_utils import camel_to_snake


class Registry(BaseContext):

    def register(self, name: str = "", add_cls: bool = True):
        def decorator(cls):
            if add_cls:
                class_name = name if name else camel_to_snake(cls.__name__)
                self._data[class_name] = cls
            return cls

        return decorator
