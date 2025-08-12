import sys

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from experiencemaker.schema.request import RetrieverRequest, SummarizerRequest, VectorStoreRequest, AgentRequest
from experiencemaker.schema.response import RetrieverResponse, SummarizerResponse, VectorStoreResponse, AgentResponse
from experiencemaker.service.experience_maker_service import ExperienceMakerService

load_dotenv()

app = FastAPI()
service = ExperienceMakerService(sys.argv[1:])


@app.post('/agent', response_model=AgentResponse)
def call_agent(request: AgentRequest):
    return service(api="agent", request=request)

@app.post('/agent', response_model=AgentResponse)
def call_fin_supply(request: AgentRequest):
    return service(api="agent", request=request)


def main():
    uvicorn.run(app=app,
                host=service.http_service_config.host,
                port=service.http_service_config.port,
                timeout_keep_alive=service.http_service_config.timeout_keep_alive,
                limit_concurrency=service.http_service_config.limit_concurrency)


if __name__ == "__main__":
    main()

# start with:
# experiencemaker \
#   http_service.port=8001 \
#   llm.default.model_name=qwen3-32b \
#   embedding_model.default.model_name=text-embedding-v4 \
#   vector_store.default.backend=local_file