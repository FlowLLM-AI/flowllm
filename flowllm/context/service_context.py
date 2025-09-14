import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from flowllm.context.base_context import BaseContext
from flowllm.context.registry import Registry
from flowllm.enumeration.registry_enum import RegistryEnum
from flowllm.schema.service_config import ServiceConfig
from flowllm.utils.singleton import singleton


@singleton
class ServiceContext(BaseContext):

    def __init__(self, service_id: str = uuid.uuid4().hex, **kwargs):
        super().__init__(**kwargs)
        self.service_id: str = service_id

        self.service_config: ServiceConfig | None = None
        self.language: str = ""
        self.thread_pool: ThreadPoolExecutor | None = None
        self.vector_store_dict: dict = {}
        self.external_mcp_tool_call_dict: dict = {}
        self.registry_dict: Dict[str, Registry] = {v: Registry() for v in RegistryEnum.__members__.values()}
        self.flow_dict: dict = {}

    """
    register model class
    """

    def register(self, name: str, register_type: RegistryEnum, register_app: str = ""):
        if register_app:
            add_cls = register_app == os.environ["FLOW_APP_NAME"]
        else:
            add_cls: bool = True
        return self.registry_dict[register_type].register(name=name, add_cls=add_cls)

    def register_embedding_model(self, name: str = ""):
        return self.register(name=name, register_type=RegistryEnum.EMBEDDING_MODEL)

    def register_llm(self, name: str = ""):
        return self.register(name=name, register_type=RegistryEnum.LLM)

    def register_vector_store(self, name: str = ""):
        return self.register(name=name, register_type=RegistryEnum.VECTOR_STORE)

    def register_op(self, name: str = "", register_app: str = ""):
        return self.register(name=name, register_type=RegistryEnum.OP, register_app=register_app)

    def register_flow(self, name: str = "", register_app: str = ""):
        return self.register(name=name, register_type=RegistryEnum.FLOW, register_app=register_app)

    def register_service(self, name: str = ""):
        return self.register(name=name, register_type=RegistryEnum.SERVICE)

    """
    get model class
    """

    def get_model_class(self, name: str, register_type: RegistryEnum, ):
        assert name in self.registry_dict[register_type], \
            f"name={name} not found in registry_dict.{register_type.value}! " \
            f"supported names={self.registry_dict[register_type].keys()}"

        return self.registry_dict[register_type][name]

    def get_embedding_model_class(self, name: str):
        return self.get_model_class(name, RegistryEnum.EMBEDDING_MODEL)

    def get_llm_class(self, name: str):
        return self.get_model_class(name, RegistryEnum.LLM)

    def get_vector_store_class(self, name: str):
        return self.get_model_class(name, RegistryEnum.VECTOR_STORE)

    def get_op_class(self, name: str):
        return self.get_model_class(name, RegistryEnum.OP)

    def get_flow_class(self, name: str):
        return self.get_model_class(name, RegistryEnum.FLOW)

    def get_service_class(self, name: str):
        return self.get_model_class(name, RegistryEnum.SERVICE)

    def get_vector_store(self, name: str = "default"):
        return self.vector_store_dict[name]

    def get_flow(self, name: str = "default"):
        return self.flow_dict[name]


C = ServiceContext()
