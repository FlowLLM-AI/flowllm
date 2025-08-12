import sys

import uvicorn
from fastapi import FastAPI

from flowllm.schema.request import AgentRequest, FinRequest
from flowllm.schema.response import AgentResponse, FinResponse
from flowllm.service.flowllm_service import FlowLLMService
from flowllm.utils.common_utils import load_env

load_env()

app = FastAPI()
service = FlowLLMService(sys.argv[1:])


@app.post('/agent', response_model=AgentResponse)
def call_agent(request: AgentRequest):
    return service(api="agent", request=request)


@app.post('/fin', response_model=FinResponse)
def call_fin(request: FinRequest):
    return service(api="fin", request=request)


def main():
    uvicorn.run(app=app,
                host=service.http_config.host,
                port=service.http_config.port,
                timeout_keep_alive=service.http_config.timeout_keep_alive,
                limit_concurrency=service.http_config.limit_concurrency)


if __name__ == "__main__":
    main()