import uuid

from flowllm.context.base_context import BaseContext
from flowllm.schema.flow_response import FlowResponse
from flowllm.schema.service_config import ServiceConfig


class FlowContext(BaseContext):

    def __init__(self, flow_id: str = uuid.uuid4().hex, **kwargs):
        super().__init__(**kwargs)
        self.flow_id: str = flow_id

    @property
    def service_config(self) -> ServiceConfig:
        return self._data.get("service_config")

    @service_config.setter
    def service_config(self, service_config: ServiceConfig):
        self._data["service_config"] = service_config

    @property
    def response(self) -> FlowResponse:
        return self._data.get("response")

    @response.setter
    def response(self, response: FlowResponse):
        self._data["response"] = response
