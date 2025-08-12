import uuid

from flowllm.context.base_context import BaseContext


class FlowContext(BaseContext):

    def __init__(self, pipeline_id: str = uuid.uuid4().hex, **kwargs):
        super().__init__(**kwargs)
        self.pipeline_id: str = pipeline_id

    @property
    def service_config(self):
        return self._data.get("service_config")
