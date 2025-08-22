import asyncio
import json
from functools import partial
from typing import Dict, Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, create_model, Field

from flowllm.context.service_context import C
from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.schema.flow_response import FlowResponse
from flowllm.schema.tool_call import ParamAttrs
from flowllm.service.base_service import BaseService
from flowllm.utils.common_utils import snake_to_camel


@C.register_service("http")
class HttpService(BaseService):
    TYPE_MAPPING = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = FastAPI(title="FlowLLM", description="HTTP API for FlowLLM")

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add health check endpoint
        self.app.get("/health")(self.health_check)

    @staticmethod
    def health_check():
        return {"status": "healthy"}

    def _create_pydantic_model(self, flow_name: str, input_schema: Dict[str, ParamAttrs]) -> BaseModel:
        fields = {}

        for param_name, param_config in input_schema.items():
            field_type = self.TYPE_MAPPING.get(param_config.type, str)

            if not param_config.required:
                fields[param_name] = (Optional[field_type], Field(default=None, description=param_config.description))
            else:
                fields[param_name] = (field_type, Field(default=..., description=param_config.description))

        return create_model(f"{snake_to_camel(flow_name)}Model", **fields)

    def integrate_tool_flow(self, tool_flow_name: str):
        tool_flow: BaseToolFlow = C.get_tool_flow(tool_flow_name)
        request_model = self._create_pydantic_model(tool_flow_name, tool_flow.tool_call.input_schema)

        async def execute_flow_endpoint(request: request_model) -> FlowResponse:
            loop = asyncio.get_event_loop()
            response: FlowResponse = await loop.run_in_executor(
                executor=C.thread_pool,
                func=partial(tool_flow.__call__, **request.model_dump()))  # noqa

            return response

        endpoint_path = f"/{tool_flow.name}"
        self.app.post(endpoint_path, response_model=FlowResponse)(execute_flow_endpoint)

    def integrate_tool_flows(self):
        super().integrate_tool_flows()

        async def execute_flow_endpoint() -> FlowResponse:
            loop = asyncio.get_event_loop()

            def list_tool_flows():
                response: FlowResponse = FlowResponse()
                tool_flow_schemas = []
                for name, tool_flow in C.tool_flow_dict.items():
                    assert isinstance(tool_flow, BaseToolFlow)
                    tool_flow_schemas.append(tool_flow.tool_call.simple_input_dump())
                response.answer = json.dumps(tool_flow_schemas, ensure_ascii=False)
                return response

            return await loop.run_in_executor(executor=C.thread_pool, func=list_tool_flows)  # noqa

        self.app.post("/list_tool_flows", response_model=FlowResponse)(execute_flow_endpoint)

    def __call__(self):
        self.integrate_tool_flows()

        uvicorn.run(self.app,
                    host=self.http_config.host,
                    port=self.http_config.port,
                    timeout_keep_alive=self.http_config.timeout_keep_alive,
                    limit_concurrency=self.http_config.limit_concurrency)
