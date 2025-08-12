import uuid
from concurrent.futures import ThreadPoolExecutor

from flowllm.context.base_context import BaseContext
from flowllm.context.registry_context import RegistryContext
from flowllm.storage.vector_store.base_vector_store import BaseVectorStore
from flowllm.utils.singleton import singleton


@singleton
class ServiceContext(BaseContext):

    def __init__(self, service_id: str = uuid.uuid4().hex, **kwargs):
        super().__init__(**kwargs)
        self.service_id: str = service_id

        self.embedding_model_registry = RegistryContext()
        self.llm_registry = RegistryContext()
        self.vector_store_registry = RegistryContext()
        self.op_registry = RegistryContext()
        self.flow_registry = RegistryContext()

    @property
    def language(self) -> str:
        return self._data.get("language")

    @language.setter
    def language(self, value: str):
        self._data["language"] = value

    @property
    def thread_pool(self) -> ThreadPoolExecutor:
        return self._data.get("thread_pool")

    @thread_pool.setter
    def thread_pool(self, thread_pool: ThreadPoolExecutor):
        self._data["thread_pool"] = thread_pool

    def get_vector_store(self, name: str = "default") -> BaseVectorStore:
        vector_store_dict: dict = self._data.get("vector_store_dict")
        if name in vector_store_dict:
            return vector_store_dict[name]
        raise KeyError(f"vector store {name} not found")

    def set_vector_stores(self, vector_store_dict: dict):
        self._data["vector_store_dict"] = vector_store_dict

    """
    register models
    """

    def register_embedding_model(self, name: str = ""):
        return self.embedding_model_registry.register(name=name)

    def register_llm(self, name: str = ""):
        return self.llm_registry.register(name=name)

    def register_vector_store(self, name: str = ""):
        return self.vector_store_registry.register(name=name)

    def register_op(self, name: str = ""):
        return self.op_registry.register(name=name)

    def register_flow(self, name: str = ""):
        return self.flow_registry.register(name=name)

    """
    resolve models
    """

    def resolve_embedding_model(self, name: str):
        assert name in self.embedding_model_registry, f"embedding_model={name} not found!"
        return self.embedding_model_registry[name]

    def resolve_llm(self, name: str):
        assert name in self.llm_registry, f"llm={name} not found!"
        return self.llm_registry[name]

    def resolve_vector_store(self, name: str):
        assert name in self.vector_store_registry, f"vector_store={name} not found!"
        return self.vector_store_registry[name]

    def resolve_op(self, name: str):
        assert name in self.op_registry, f"op={name} not found!"
        return self.op_registry[name]

    def resolve_flow(self, name: str):
        assert name in self.flow_registry, f"flow={name} not found!"
        return self.flow_registry[name]


C = ServiceContext()
