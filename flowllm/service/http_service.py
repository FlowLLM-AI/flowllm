import asyncio
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger

from flowllm.context.service_context import C
from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.schema.flow_response import FlowResponse
from flowllm.schema.flow_stream_chunk import FlowStreamChunk
from flowllm.service.base_service import BaseService


@C.register_service("http")
class HttpService(BaseService):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = FastAPI(title="FlowLLM", description="HTTP API for FlowLLM")
        self.app.add_middleware(CORSMiddleware,
                                allow_origins=["*"],
                                allow_credentials=True,
                                allow_methods=["*"],
                                allow_headers=["*"])

        self.app.get("/health")(self.health_check)

    @staticmethod
    def health_check():
        return {"status": "healthy"}

    def integrate_flow(self, tool_flow: BaseToolFlow):
        if "http" not in tool_flow.service_type:
            return

        request_model = self._create_pydantic_model(tool_flow.name, tool_flow.tool_call.input_schema)

        async def execute_endpoint(request: request_model) -> FlowResponse:
            return await tool_flow(**request.model_dump())

        self.app.post(f"/{tool_flow.name}", response_model=FlowResponse)(execute_endpoint)

    @staticmethod
    def gen_stream_response(queue: asyncio.Queue):
        async def generate_stream() -> AsyncGenerator[bytes, None]:
            while True:
                stream_chunk: FlowStreamChunk = await queue.get()
                if stream_chunk.done:
                    yield f"data:[DONE]\n\n".encode('utf-8')
                    break
                else:
                    yield f"data:{stream_chunk.model_dump_json()}\n\n".encode("utf-8")

        return StreamingResponse(generate_stream(), media_type="text/event-stream")

    def integrate_stream_flow(self, tool_flow: BaseToolFlow):
        if "http" not in tool_flow.service_type:
            return

        request_model = self._create_pydantic_model(tool_flow.name, tool_flow.tool_call.input_schema)

        async def execute_stream_endpoint(request: request_model) -> StreamingResponse:
            stream_queue = asyncio.Queue()
            asyncio.create_task(tool_flow(stream_queue=stream_queue, **request.model_dump()))
            return self.gen_stream_response(stream_queue)

        self.app.post(f"/{tool_flow.name}")(execute_stream_endpoint)

    def integrate_flows(self):
        super().integrate_flows()

        async def execute_endpoint() -> list:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(executor=C.thread_pool, func=C.list_flow_schemas)  # noqa

        endpoint_path = "list"
        self.app.get(f"/{endpoint_path}", response_model=list)(execute_endpoint)
        logger.info(f"integrate endpoint={endpoint_path}")

    def execute(self):
        uvicorn.run(self.app,
                    host=self.http_config.host,
                    port=self.http_config.port,
                    timeout_keep_alive=self.http_config.timeout_keep_alive,
                    limit_concurrency=self.http_config.limit_concurrency)
