from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from loguru import logger
from mcp.types import TextContent

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.flow_engine.base_flow_engine import BaseFlowEngine
from flowllm.schema.flow_response import FlowResponse
from flowllm.schema.service_config import ServiceConfig, EmbeddingModelConfig, FlowConfig


class BaseService:

    def __init__(self, service_config: ServiceConfig):
        self.service_config = service_config

        C.language = self.service_config.language
        C.thread_pool = ThreadPoolExecutor(max_workers=self.service_config.thread_pool_max_workers)
        for name, config in self.service_config.vector_store.items():
            vector_store_cls = C.resolve_vector_store(config.backend)
            embedding_model_config: EmbeddingModelConfig = self.service_config.embedding_model[config.embedding_model]
            embedding_model_cls = C.resolve_embedding_model(embedding_model_config.backend)
            embedding_model = embedding_model_cls(model_name=embedding_model_config.model_name,
                                                  **embedding_model_config.params)
            C.set_vector_store(name, vector_store_cls(embedding_model=embedding_model, **config.params))

        self.flow_engine_config = self.service_config.flow_engine
        self.flow_engine_cls = C.resolve_flow_engine(self.flow_engine_config.backend)
        self.flow_config_dict: Dict[str, FlowConfig] = \
            {name: config.set_name(name) for name, config in self.service_config.flow.items()}

        self.mcp_config = self.service_config.mcp
        self.http_config = self.service_config.http

    def execute_flow(self, flow_name: str, **kwargs) -> FlowResponse:
        response = FlowResponse()
        try:
            logger.info(f"request.params={kwargs}")
            flow_context = FlowContext(service_config=self.service_config.model_copy(deep=True),
                                       response=response, **kwargs)

            flow_config = self.flow_config_dict[flow_name]
            flow_engine: BaseFlowEngine = self.flow_engine_cls(flow_name=flow_name,
                                                               flow_content=flow_config.flow_content,
                                                               flow_context=flow_context,
                                                               **self.flow_engine_config.params)
            flow_engine()

        except Exception as e:
            logger.exception(f"flow_name={flow_name} encounter error={e.args}")
            response.isError = True
            response.content.append(TextContent(text=str(e.args), type="text"))

        return response

    def __call__(self):
        raise NotImplementedError
