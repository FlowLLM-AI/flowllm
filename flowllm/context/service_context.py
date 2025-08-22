import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from flowllm.context.base_context import BaseContext
from flowllm.context.registry import Registry
from flowllm.schema.service_config import ServiceConfig
from flowllm.utils.singleton import singleton


@singleton
class ServiceContext(BaseContext):

    def __init__(self, service_id: str = uuid.uuid4().hex, **kwargs):
        super().__init__(**kwargs)
        self.service_id: str = service_id
        self.registry_dict: Dict[str, Registry] = \
            {k: Registry(k) for k in ["embedding_model", "llm", "vector_store", "op", "flow_engine", "service"]}

    @property
    def language(self) -> str:
        return self._data.get("language", "")

    @language.setter
    def language(self, value: str):
        self._data["language"] = value

    @property
    def thread_pool(self) -> ThreadPoolExecutor:
        return self._data["thread_pool"]

    @thread_pool.setter
    def thread_pool(self, thread_pool: ThreadPoolExecutor):
        self._data["thread_pool"] = thread_pool

    @property
    def service_config(self) -> ServiceConfig:
        return self._data.get("service_config")

    @service_config.setter
    def service_config(self, service_config: ServiceConfig):
        self._data["service_config"] = service_config

    def get_vector_store(self, name: str = "default"):
        vector_store_dict: dict = self._data["vector_store_dict"]
        if name not in vector_store_dict:
            raise KeyError(f"vector store {name} not found")

        return vector_store_dict[name]

    def set_vector_store(self, name: str, vector_store):
        if "vector_store_dict" not in self._data:
            self.set_vector_stores({})

        self._data["vector_store_dict"][name] = vector_store

    def set_vector_stores(self, vector_store_dict: dict):
        self._data["vector_store_dict"] = vector_store_dict

    """
    register models
    """

    def register_embedding_model(self, name: str = ""):
        return self.registry_dict["embedding_model"].register(name=name)

    def register_llm(self, name: str = ""):
        return self.registry_dict["llm"].register(name=name)

    def register_vector_store(self, name: str = ""):
        return self.registry_dict["vector_store"].register(name=name)

    def register_op(self, name: str = ""):
        return self.registry_dict["op"].register(name=name)

    def register_flow_engine(self, name: str = ""):
        return self.registry_dict["flow_engine"].register(name=name)

    def register_service(self, name: str = ""):
        return self.registry_dict["service"].register(name=name)

    """
    resolve models
    """

    def resolve_embedding_model(self, name: str):
        assert name in self.registry_dict["embedding_model"], f"embedding_model={name} not found!"
        return self.registry_dict["embedding_model"][name]

    def resolve_llm(self, name: str):
        assert name in self.registry_dict["llm"], f"llm={name} not found!"
        return self.registry_dict["llm"][name]

    def resolve_vector_store(self, name: str):
        assert name in self.registry_dict["vector_store"], f"vector_store={name} not found!"
        return self.registry_dict["vector_store"][name]

    def resolve_op(self, name: str):
        assert name in self.registry_dict["op"], f"op={name} not found!"
        return self.registry_dict["op"][name]

    def resolve_flow_engine(self, name: str):
        assert name in self.registry_dict["flow_engine"], f"flow={name} not found!"
        return self.registry_dict["flow_engine"][name]

    def resolve_service(self, name: str):
        assert name in self.registry_dict["service"], f"service={name} not found!"
        return self.registry_dict["service"][name]



C = ServiceContext()
