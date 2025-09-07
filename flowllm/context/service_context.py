import asyncio
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from inspect import isclass
from typing import Dict, List

from fastmcp import Client
from loguru import logger

from flowllm.context.base_context import BaseContext
from flowllm.context.registry import Registry
from flowllm.schema.service_config import ServiceConfig, EmbeddingModelConfig
from flowllm.schema.tool_call import ToolCall
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
        self.sse_mcp_dict: dict = {}

        self.registry_dict: Dict[str, Registry] = {}
        use_framework: bool = os.environ.get("FLOW_USE_FRAMEWORK", "").lower() == "true"
        for key in ["embedding_model", "llm", "vector_store", "op", "tool_flow", "service"]:
            enable_log = True
            register_flow_module = True

            if use_framework:
                enable_log = False
                if key in ["op", "tool_flow"]:
                    register_flow_module = False
            self.registry_dict[key] = Registry(key, enable_log=enable_log, register_flow_module=register_flow_module)

        self.flow_dict: dict = {}

    def set_service_config(self, parser=None, config_name: str = "config=base"):
        if parser is None:
            from flowllm.config.pydantic_config_parser import PydanticConfigParser
            parser = PydanticConfigParser

        config_parser = parser(ServiceConfig)
        self.service_config = config_parser.parse_args(config_name)
        return self

    @staticmethod
    async def get_sse_mcp_dict(hosts: List[str]):
        tool_call_dict = {}

        for host in hosts:
            async with Client(f"{host}/sse/") as client:
                tools = await client.list_tools()
                for tool in tools:
                    tool_call = ToolCall.from_mcp_tool(tool)
                    key = host + "/" + tool.name
                    tool_call_dict[key] = tool_call
                    logger.info(f"{host} find mcp_name={key} "
                                f"tool_call={json.dumps(tool_call.simple_input_dump(), ensure_ascii=False)}")
        return tool_call_dict

    def prepare_sse_mcp(self):
        hosts = os.getenv("FLOW_MCP_HOSTS")
        if not hosts:
            return self

        hosts = [x.strip() for x in hosts.strip().split(",") if x.strip()]
        if not hosts:
            return self

        self.sse_mcp_dict = asyncio.run(self.get_sse_mcp_dict(hosts))
        return self

    def filter_flows(self, name: str) -> bool:
        if self.service_config.enabled_flows:
            return name in self.service_config.enabled_flows
        elif self.service_config.disabled_flows:
            return name not in self.service_config.disabled_flows
        else:
            return True

    def init_by_service_config(self, service_config: ServiceConfig = None):
        if service_config:
            self.service_config = service_config

        self.language = self.service_config.language
        self.thread_pool = ThreadPoolExecutor(max_workers=self.service_config.thread_pool_max_workers)
        if self.service_config.ray_max_workers > 1:
            import ray
            ray.init(num_cpus=self.service_config.ray_max_workers)

        # add vector store
        for name, config in self.service_config.vector_store.items():
            vector_store_cls = self.resolve_vector_store(config.backend)
            embedding_model_config: EmbeddingModelConfig = self.service_config.embedding_model[config.embedding_model]
            embedding_model_cls = self.resolve_embedding_model(embedding_model_config.backend)
            embedding_model = embedding_model_cls(model_name=embedding_model_config.model_name,
                                                  **embedding_model_config.params)
            self.vector_store_dict[name] = vector_store_cls(embedding_model=embedding_model, **config.params)

        from flowllm.flow.base_tool_flow import BaseToolFlow
        from flowllm.flow.expression.expression_tool_flow import ExpressionToolFlow

        # add tool flow cls
        for name, tool_flow_cls in self.registry_dict["tool_flow"].items():
            if not isclass(tool_flow_cls):
                continue

            if not self.filter_flows(name):
                continue

            tool_flow: BaseToolFlow = tool_flow_cls()
            self.flow_dict[tool_flow.name] = tool_flow
            logger.info(f"add cls tool_flow: {tool_flow.name}")

        # add tool flow config
        for name, flow_config in self.service_config.flow.items():
            if not self.filter_flows(name):
                continue

            flow_config.name = name
            tool_flow: BaseToolFlow = ExpressionToolFlow(flow_config=flow_config)
            self.flow_dict[tool_flow.name] = tool_flow
            logger.info(f"add expression tool_flow:{tool_flow.name}")

    def stop_by_service_config(self, wait_thread_pool=True, wait_ray: bool = True):
        self.thread_pool.shutdown(wait=wait_thread_pool)
        if self.service_config.ray_max_workers > 1:
            import ray
            ray.shutdown(_exiting_interpreter=not wait_ray)

        from flowllm.storage.vector_store.base_vector_store import BaseVectorStore
        for name, vector_store in self.vector_store_dict.items():
            assert isinstance(vector_store, BaseVectorStore)
            vector_store.close()

    def get_vector_store(self, name: str = "default"):
        return self.vector_store_dict[name]

    def get_tool_flow(self, name: str = "default"):
        return self.flow_dict[name]

    @property
    def tool_flow_names(self) -> List[str]:
        return sorted(self.flow_dict.keys())

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

    @staticmethod
    def list_flow_schemas() -> List[dict]:
        from flowllm.flow.base_tool_flow import BaseToolFlow

        flow_schemas = []
        for name, tool_flow in C.flow_dict.items():
            assert isinstance(tool_flow, BaseToolFlow)
            flow_schemas.append(tool_flow.tool_call.simple_input_dump())
        return flow_schemas


C = ServiceContext()
