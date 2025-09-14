import asyncio
import os
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from flowllm.context.service_context import C
from flowllm.flow import BaseFlow
from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.schema.flow_response import FlowResponse
from flowllm.schema.flow_stream_chunk import FlowStreamChunk
from flowllm.service.base_service import BaseService
from flowllm.utils.pydantic_utils import create_pydantic_model


@C.register_service("http")
class HttpService(BaseService):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = FastAPI(title=os.environ["FLOW_APP_NAME"])
        self.app.add_middleware(CORSMiddleware,
                                allow_origins=["*"],
                                allow_credentials=True,
                                allow_methods=["*"],
                                allow_headers=["*"])

        def health_check():
            return {"status": "healthy"}

        self.app.get("/health")(health_check)

    def integrate_flow(self, flow: BaseFlow) -> bool:
        request_model = create_pydantic_model(flow.name)

        async def execute_endpoint(request: request_model) -> FlowResponse:
            return await flow.async_call(**request.model_dump())

        self.app.post(f"/{flow.name}", response_model=FlowResponse)(execute_endpoint)
        return True

    def integrate_tool_flow(self, flow: BaseToolFlow) -> bool:
        request_model = create_pydantic_model(flow.name, input_schema=flow.tool_call.input_schema)

        async def execute_endpoint(request: request_model) -> FlowResponse:
            return await flow.async_call(**request.model_dump())

        self.app.post(f"/{flow.name}", response_model=FlowResponse)(execute_endpoint)
        return True

    def integrate_stream_flow(self, flow: BaseFlow) -> bool:
        request_model = create_pydantic_model(flow.name)

        async def execute_stream_endpoint(request: request_model) -> StreamingResponse:
            stream_queue = asyncio.Queue()
            asyncio.create_task(flow.async_call(stream_queue=stream_queue, **request.model_dump()))

            async def generate_stream() -> AsyncGenerator[bytes, None]:
                while True:
                    stream_chunk: FlowStreamChunk = await stream_queue.get()
                    if stream_chunk.done:
                        yield f"data:[DONE]\n\n".encode('utf-8')
                        break
                    else:
                        yield f"data:{stream_chunk.model_dump_json()}\n\n".encode("utf-8")

            return StreamingResponse(generate_stream(), media_type="text/event-stream")

        self.app.post(f"/{flow.name}")(execute_stream_endpoint)
        return True

    def run(self):
        super().run()
        http_config = self.service_config.http
        uvicorn.run(self.app,
                    host=http_config.host,
                    port=http_config.port,
                    timeout_keep_alive=http_config.timeout_keep_alive,
                    limit_concurrency=http_config.limit_concurrency)
