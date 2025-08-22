import uuid

from flowllm.context.base_context import BaseContext
from flowllm.schema.flow_response import FlowResponse


class FlowContext(BaseContext):

    def __init__(self,
                 flow_id: str = uuid.uuid4().hex,
                 response: FlowResponse = None,
                 **kwargs):
        super().__init__(**kwargs)

        self.flow_id: str = flow_id
        self.response: FlowResponse = FlowResponse() if response is None else response
