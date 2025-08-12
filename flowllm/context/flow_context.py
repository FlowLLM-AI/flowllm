import uuid

from flowllm.context.base_context import BaseContext
from flowllm.schema.request import BaseRequest
from flowllm.schema.response import BaseResponse
from flowllm.schema.service_config import ServiceConfig


class FlowContext(BaseContext):

    def __init__(self, pipeline_id: str = uuid.uuid4().hex, **kwargs):
        super().__init__(**kwargs)
        self.pipeline_id: str = pipeline_id

    @property
    def service_config(self) -> ServiceConfig:
        return self._data.get("service_config")

    @service_config.setter
    def service_config(self, value: ServiceConfig):
        self._data["service_config"] = value

    @property
    def request(self):
        return self._data.get("request")

    @request.setter
    def request(self, value: BaseRequest):
        self._data["request"] = value

    @property
    def response(self):
        return self._data.get("response")

    @response.setter
    def response(self, value: BaseResponse):
        self._data["response"] = value
