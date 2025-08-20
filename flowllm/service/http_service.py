from typing import Dict, Any, Optional
import asyncio
from functools import partial
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, create_model, Field

from flowllm.context.service_context import C
from flowllm.service.base_service import BaseService
from flowllm.schema.tool_call import ParamAttrs
from flowllm.utils.common_utils import snake_to_camel


class FlowRequest(BaseModel):
    """Base request model for flows"""
    pass


class FlowResponseModel(BaseModel):
    """Response model for flow execution"""
    success: bool
    answer: str
    error: str = ""


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
        self.app = FastAPI(
            title="FlowLLM HTTP Service",
            description="HTTP API for FlowLLM flows",
            version="1.0.0"
        )
        
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
        
    def health_check(self):
        """Health check endpoint"""
        return {"status": "healthy", "service": "FlowLLM HTTP Service"}
    
    def _create_pydantic_model(self, flow_name: str, input_schema: Dict[str, ParamAttrs]) -> BaseModel:
        """Create a dynamic Pydantic model based on flow input schema"""
        fields = {}

        for param_name, param_config in input_schema.items():
            field_type = self.TYPE_MAPPING.get(param_config.type, str)

            if not param_config.required:
                fields[param_name] = (Optional[field_type], Field(default=None, description=param_config.description))
            else:
                fields[param_name] = (field_type, Field(default=..., description=param_config.description))

        return create_model(f"{snake_to_camel(flow_name)}Model", **fields)
    
    def register_flow(self, flow_name: str):
        """Register a flow as an HTTP endpoint"""
        flow_config = self.flow_config_dict[flow_name]
        
        # Create dynamic request model based on flow input schema
        request_model = self._create_pydantic_model(flow_name, flow_config.input_schema)
        
        async def execute_flow_endpoint(request: request_model):
            """Execute flow endpoint"""
            try:
                # Convert request to dict
                kwargs = request.dict() if hasattr(request, 'dict') else {}
                
                # 使用线程池异步执行flow，避免阻塞事件循环
                loop = asyncio.get_event_loop()
                execute_with_args = partial(self.execute_flow, flow_name, **kwargs)
                response = await loop.run_in_executor(
                    C.thread_pool,
                    execute_with_args
                )
                
                if response.isError:
                    error_msg = ""
                    if response.content:
                        error_msg = " ".join([content.text for content in response.content if hasattr(content, 'text')])
                    
                    return FlowResponseModel(
                        success=False,
                        answer="",
                        error=error_msg or "Unknown error occurred"
                    )
                
                return FlowResponseModel(
                    success=True,
                    answer=response.answer,
                    error=""
                )
                
            except Exception as e:
                logger.exception(f"Error executing flow {flow_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Register the endpoint
        endpoint_path = f"/flow/{flow_name}"
        self.app.post(endpoint_path, response_model=FlowResponseModel)(execute_flow_endpoint)
        
        logger.info(f"Registered flow={flow_name} at endpoint={endpoint_path}")
    
    def __call__(self):
        """Start the HTTP service"""
        # Register all flows as endpoints
        for flow_name in self.flow_config_dict.keys():
            self.register_flow(flow_name)
        
        # Start the server
        uvicorn.run(
            self.app,
            host=self.http_config.host,
            port=self.http_config.port,
            timeout_keep_alive=self.http_config.timeout_keep_alive,
            limit_concurrency=self.http_config.limit_concurrency
        )
