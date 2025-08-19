import uuid

from pydantic import BaseModel

from flowllm.context.base_context import BaseContext
from flowllm.schema.flow_io import FlowRequest, FlowResponse
from flowllm.schema.service_config import ServiceConfig


class FlowContext(BaseContext):

    def __init__(self, flow_id: str = uuid.uuid4().hex, **kwargs):
        super().__init__(**kwargs)
        self.flow_id: str = flow_id

    @property
    def service_config(self) -> ServiceConfig:
        return self._data.get("service_config")

    @service_config.setter
    def service_config(self, value: ServiceConfig):
        self._data["service_config"] = value

    @property
    def request(self) -> BaseModel:
        return self._data.get("request")

    @request.setter
    def request(self, value: BaseModel):
        self._data["request"] = value

    @property
    def response(self) -> FlowResponse:
        return self._data.get("response")

    @response.setter
    def response(self, value: FlowResponse):
        self._data["response"] = value
