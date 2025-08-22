import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

from loguru import logger

from flowllm.context.base_context import BaseContext
from flowllm.context.registry import Registry
from flowllm.schema.service_config import ServiceConfig, EmbeddingModelConfig
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

        self.registry_dict: Dict[str, Registry] = \
            {k: Registry(k) for k in ["embedding_model", "llm", "vector_store", "op", "tool_flow", "service"]}
        self.tool_flow_dict: dict = {}

    def set_default_service_config(self):
        from flowllm.config.pydantic_config_parser import PydanticConfigParser

        config_parser = PydanticConfigParser(ServiceConfig)
        self.service_config = config_parser.parse_args("config=default_config")
        return self

    def init_by_service_config(self, service_config: ServiceConfig):
        self.service_config = service_config
        self.language = self.service_config.language
        self.thread_pool = ThreadPoolExecutor(max_workers=self.service_config.thread_pool_max_workers)

        # add vector store
        for name, config in self.service_config.vector_store.items():
            vector_store_cls = self.resolve_vector_store(config.backend)
            embedding_model_config: EmbeddingModelConfig = self.service_config.embedding_model[config.embedding_model]
            embedding_model_cls = self.resolve_embedding_model(embedding_model_config.backend)
            embedding_model = embedding_model_cls(model_name=embedding_model_config.model_name,
                                                  **embedding_model_config.params)
            self.vector_store_dict[name] = vector_store_cls(embedding_model=embedding_model, **config.params)

        from flowllm.flow.base_tool_flow import BaseToolFlow
        from flowllm.flow.gallery import ExpressionToolFlow

        for name, tool_flow_cls in self.registry_dict["tool_flow"]:
            tool_flow: BaseToolFlow = tool_flow_cls()
            self.tool_flow_dict[tool_flow.name] = tool_flow
            logger.info(f"add diy tool_flow={tool_flow.name}")

        for name, flow_config in self.service_config.flow.items():
            flow_config.name = name
            tool_flow: BaseToolFlow = ExpressionToolFlow()
            self.tool_flow_dict[tool_flow.name] = tool_flow
            logger.info(f"add expression tool_flow={tool_flow.name}")

    def get_vector_store(self, name: str = "default"):
        return self.vector_store_dict[name]

    def get_tool_flow(self, name: str = "default"):
        return self.tool_flow_dict[name]

    @property
    def tool_flow_names(self) -> List[str]:
        return sorted(self.tool_flow_dict.keys())

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

    def register_tool_flow(self, name: str = ""):
        return self.registry_dict["tool_flow"].register(name=name)

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

    def resolve_tool_flow(self, name: str):
        assert name in self.registry_dict["tool_flow"], f"tool_flow={name} not found!"
        return self.registry_dict["tool_flow"][name]

    def resolve_service(self, name: str):
        assert name in self.registry_dict["service"], f"service={name} not found!"
        return self.registry_dict["service"][name]


C = ServiceContext()
