from loguru import logger

from flowllm.context.base_context import BaseContext
from flowllm.utils.common_utils import camel_to_snake


class RegistryContext(BaseContext):

    def __init__(self, enable_log: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.enable_log: bool = enable_log

    def register(self, name: str = ""):
        def decorator(cls):
            class_name = name if name else camel_to_snake(cls.__name__)
            if self.enable_log:
                if class_name in self._data:
                    logger.warning(f"class({class_name}) is already registered!")
                else:
                    logger.info(f"class({class_name}) is registered.")
            self._data[class_name] = cls
            return cls

        return decorator


EMBEDDING_MODEL_REGISTRY = RegistryContext()
LLM_REGISTRY = RegistryContext()
VECTOR_STORE_REGISTRY = RegistryContext()
OP_REGISTRY = RegistryContext()
PIPELINE_REGISTRY = RegistryContext()


def register_embedding_model(name: str = ""):
    return EMBEDDING_MODEL_REGISTRY.register(name=name)


def register_llm(name: str = ""):
    return LLM_REGISTRY.register(name=name)


def register_vector_store(name: str = ""):
    return VECTOR_STORE_REGISTRY.register(name=name)


def register_op(name: str = ""):
    return OP_REGISTRY.register(name=name)


def register_pipeline(name: str = ""):
    return PIPELINE_REGISTRY.register(name=name)
