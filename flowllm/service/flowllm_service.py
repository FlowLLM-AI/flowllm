from concurrent.futures import ThreadPoolExecutor
from typing import List

from loguru import logger

from flowllm.config.config_parser import ConfigParser
from flowllm.context.registry_context import get_vector_store, get_embedding_model
from flowllm.context.service_context import C, ServiceContext
from flowllm.schema.request import BaseRequest, AgentRequest
from flowllm.schema.response import BaseResponse, AgentResponse
from flowllm.schema.service_config import ServiceConfig, EmbeddingModelConfig


class FlowLLMService:

    def __init__(self, args: List[str]):
        self.config_parser = ConfigParser(args)
        self.init_config: ServiceConfig = self.config_parser.get_service_config()
        self.service_context: ServiceContext = C

        self.service_context.update({
            "language": self.init_config.g.language,
            "thread_pool": ThreadPoolExecutor(max_workers=self.init_config.g.thread_pool_max_workers),
            "vector_store_dict": {},
        })

        for name, config in self.init_config.vector_store.items():
            vector_store_cls = get_vector_store(config.backend)
            embedding_model_config: EmbeddingModelConfig = self.init_config.embedding_model[config.embedding_model]
            embedding_model_cls = get_embedding_model(embedding_model_config.backend)
            embedding_model = embedding_model_cls(model_name=embedding_model_config.model_name,
                                                  **embedding_model_config.params)
            self.service_context["vector_store_dict"][name] = vector_store_cls(embedding_model=embedding_model,
                                                                               **config.params)

    def __call__(self, api: str, request: dict | BaseRequest) -> BaseResponse:
        if isinstance(request, dict):
            config = self.config_parser.get_service_config(**request["config"])
        else:
            config = self.config_parser.get_service_config(**request.config)

        if api == "agent":
            if isinstance(request, dict):
                request = AgentRequest(**request)
            response = AgentResponse()
            pipeline = config.flow

        elif api == "fin_supply":
            if isinstance(request, dict):
                request = AgentRequest(**request)
            response = AgentResponse()
            pipeline = config.flow

        else:
            raise RuntimeError(f"Invalid service.api={api}")

        logger.info(f"request={request.model_dump_json()}")

        try:
            context = PipelineContext(app_config=config,
                                      thread_pool=self.thread_pool,
                                      request=request,
                                      response=response,
                                      vector_store_dict=self.vector_store_dict)
            pipeline = Pipeline(pipeline=pipeline, context=context)
            pipeline()

        except Exception as e:
            logger.exception(f"api={api} encounter error={e.args}")
            response.success = False
            response.metadata["error"] = str(e)

        return response
