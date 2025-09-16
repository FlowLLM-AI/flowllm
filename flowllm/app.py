import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import List

from loguru import logger

from flowllm.client.mcp_client import McpClient
from flowllm.config.pydantic_config_parser import PydanticConfigParser
from flowllm.context import C
from flowllm.enumeration.registry_enum import RegistryEnum
from flowllm.flow.base_flow import BaseFlow
from flowllm.flow.expression_tool_flow import ExpressionToolFlow
from flowllm.schema.flow_stream_chunk import FlowStreamChunk
from flowllm.schema.service_config import EmbeddingModelConfig, ServiceConfig
from flowllm.service.base_service import BaseService
from flowllm.utils.logger_utils import init_logger


class FlowLLMApp:

    def __init__(self,
                 args: List[str] = None,
                 service_config: ServiceConfig = None,
                 parser: type[PydanticConfigParser] = None,
                 load_default_config: bool = False):
        if service_config is not None:
            self.service_config: ServiceConfig = service_config

        else:
            if parser is None:
                parser = PydanticConfigParser

            if load_default_config:
                args = [f"config={parser.default_config_name}"]
            elif isinstance(args, str):
                args = [x for x in args.split(" ") if x]
            elif not args:
                args = []

            self.service_config = parser(ServiceConfig).parse_args(*args)

        if self.service_config.init_logger:
            init_logger()

    async def __aenter__(self):
        await self.async_start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.async_stop()
        return False

    @staticmethod
    async def get_mcp_tools(name: str, mcp_server_config: dict) -> dict:
        async with McpClient(name=name, config=mcp_server_config) as client:
            tool_calls = await client.list_tool_calls()
            for tool_call in tool_calls:
                logger.info(f"find mcp@{name}@{tool_call.name} {str(tool_call.model_dump_json())[:200]}...")

            return {
                "name": name,
                "tool_calls": {tool_call.name: tool_call for tool_call in tool_calls}
            }

    def filter_flows(self, name: str) -> bool:
        if self.service_config.enabled_flows:
            return name in self.service_config.enabled_flows
        elif self.service_config.disabled_flows:
            return name not in self.service_config.disabled_flows
        else:
            return True

    async def async_start(self):
        # add external_mcp
        coro_list = []
        for name, mcp_server_config in self.service_config.external_mcp.items():
            coro_list.append(self.get_mcp_tools(name, mcp_server_config))
        if coro_list:
            for mcp_server_info in await asyncio.gather(*coro_list):
                C.external_mcp_tool_call_dict[mcp_server_info["name"]] = mcp_server_info["tool_calls"]

        # add service_config & language & thread_pool & ray
        C.service_config = self.service_config
        C.language = self.service_config.language
        C.thread_pool = ThreadPoolExecutor(max_workers=self.service_config.thread_pool_max_workers)
        if self.service_config.ray_max_workers > 1:
            import ray
            ray.init(num_cpus=self.service_config.ray_max_workers)

        # add vector store
        for name, config in self.service_config.vector_store.items():
            vector_store_cls = C.get_vector_store_class(config.backend)
            embedding_model_config: EmbeddingModelConfig = self.service_config.embedding_model[
                config.embedding_model]
            embedding_model_cls = C.get_embedding_model_class(embedding_model_config.backend)
            embedding_model = embedding_model_cls(model_name=embedding_model_config.model_name,
                                                  **embedding_model_config.params)
            C.vector_store_dict[name] = vector_store_cls(embedding_model=embedding_model, **config.params)

        # add cls flow
        for name, flow_cls in C.registry_dict[RegistryEnum.FLOW].items():
            if not self.filter_flows(name):
                continue

            flow: BaseFlow = flow_cls()
            C.flow_dict[flow.name] = flow

        # add expression flow
        for name, flow_config in self.service_config.flow.items():
            if not self.filter_flows(name):
                continue

            flow_config.name = name
            flow: BaseFlow = ExpressionToolFlow(flow_config=flow_config)
            C.flow_dict[name] = flow

    async def async_stop(self, wait_thread_pool=True, wait_ray: bool = True):
        C.thread_pool.shutdown(wait=wait_thread_pool)
        if self.service_config.ray_max_workers > 1:
            import ray
            ray.shutdown(_exiting_interpreter=not wait_ray)
        for name, vector_store in C.vector_store_dict.items():
            await vector_store.async_close()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False

    def start(self):
        asyncio.run(self.async_start())

    def stop(self, wait_thread_pool=True, wait_ray: bool = True):
        C.thread_pool.shutdown(wait=wait_thread_pool)
        if self.service_config.ray_max_workers > 1:
            import ray
            ray.shutdown(_exiting_interpreter=not wait_ray)
        for name, vector_store in C.vector_store_dict.items():
            vector_store.close()

    @staticmethod
    def execute_flow(name: str, **kwargs):
        flow: BaseFlow = C.get_flow(name)
        assert flow.stream is False, "stream is not supported in async_execute_flow!"
        return flow.call(**kwargs)

    @staticmethod
    async def async_execute_flow(name: str, **kwargs):
        flow: BaseFlow = C.get_flow(name)
        assert flow.stream is False, "stream is not supported in async_execute_flow!"
        return await flow.async_call(**kwargs)

    @staticmethod
    async def async_execute_stream_flow(name: str, **kwargs):
        flow: BaseFlow = C.get_flow(name)
        assert flow.stream is True, "non-stream is not supported in async_execute_stream_flow!"

        stream_queue = asyncio.Queue()
        asyncio.create_task(flow.async_call(stream_queue=stream_queue, **kwargs))
        while True:
            stream_chunk: FlowStreamChunk = await stream_queue.get()
            if stream_chunk.done:
                yield f"data:[DONE]\n\n"
                break
            else:
                yield f"data:{stream_chunk.model_dump_json()}\n\n"

    def run_service(self):
        service_cls = C.get_service_class(self.service_config.backend)
        service: BaseService = service_cls(service_config=self.service_config,
                                           enable_logo=self.service_config.enable_logo)
        service.run()



def main():
    with FlowLLMApp(args=sys.argv[1:]) as app:
        app.run_service()


if __name__ == "__main__":
    main()

# python -m build && twine upload dist/*
