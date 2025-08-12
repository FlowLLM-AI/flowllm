import uuid

from flowllm.context.base_context import BaseContext


class PipelineContext(BaseContext):

    def __init__(self, pipeline_id: str = uuid.uuid4().hex, **kwargs):
        super().__init__(**kwargs)
        self.pipeline_id: str = pipeline_id
