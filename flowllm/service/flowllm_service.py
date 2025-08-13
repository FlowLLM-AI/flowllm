from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import List, Dict

from loguru import logger
from fastmcp.tools import Tool, FunctionTool

from flowllm.config.config_parser import ConfigParser
from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.flow.base_flow_engine import BaseFlowEngine
from flowllm.schema.flow_io import FlowRequest, FlowResponse
from flowllm.schema.service_config import ServiceConfig, EmbeddingModelConfig, HttpConfig


class FlowLLMService:

    def __init__(self, args: List[str]):
        self.config_parser = ConfigParser(args)
        self.init_config: ServiceConfig = self.config_parser.get_service_config()

        C.language = self.init_config.language
        C.thread_pool = ThreadPoolExecutor(max_workers=self.init_config.thread_pool_max_workers)
        for name, config in self.init_config.vector_store.items():
            vector_store_cls = C.resolve_vector_store(config.backend)
            embedding_model_config: EmbeddingModelConfig = self.init_config.embedding_model[config.embedding_model]
            embedding_model_cls = C.resolve_embedding_model(embedding_model_config.backend)
            embedding_model = embedding_model_cls(model_name=embedding_model_config.model_name,
                                                  **embedding_model_config.params)
            C.set_vector_store(name, vector_store_cls(embedding_model=embedding_model, **config.params))

    @property
    def http_config(self) -> HttpConfig:
        return self.init_config.http

    @property
    def mcp_config_dict(self) -> dict:
        return asdict(self.init_config.mcp)

    def execute_flow(self):
        service_config = self.config_parser.get_service_config()
        flow_engine_config = service_config.flow_engine
        flow_engine_cls = C.resolve_flow_engine(flow_engine_config.backend)
        flow_engine_cls()

    # @property
    # def mcp_tool_dict(self) -> Dict[str, Tool]:
    #
    #
    #     for name, flow_meta in service_config.flow_engine.flow_meta_dict.items():
    #         tool = FunctionTool(fn=)

    def __call__(self, api: str, request: dict | FlowRequest) -> FlowResponse:
        if isinstance(request, dict):
            request = FlowRequest(**request)
        logger.info(f"request={request.model_dump_json()}")
        response = FlowResponse()
        service_config = self.config_parser.get_service_config(**request.service_config)

        try:
            assert request.flow_name in service_config.flow_engine.flow_dict, f"flow={request.flow_name} not found"
            flow_content = service_config.flow_engine.flow_dict[request.flow_name]

            flow_context = FlowContext()
            flow_context.service_config = service_config
            flow_context.request = request
            flow_context.response = response

            flow_engine_cls = C.resolve_flow_engine(service_config.flow_engine.backend)
            flow_engine: BaseFlowEngine = flow_engine_cls(flow_name=request.flow_name,
                                                          flow_content=flow_content,
                                                          flow_context=flow_context)
            flow_engine()

        except Exception as e:
            logger.exception(f"api={api} encounter error={e.args}")
            response.success = False
            response.metadata["error"] = str(e)

        return response
