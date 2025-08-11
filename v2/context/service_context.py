import uuid
from concurrent.futures import ThreadPoolExecutor

from v2.context.base_context import BaseContext


class ServiceContext(BaseContext):

    def __init__(self, service_id: str = uuid.uuid4().hex, **kwargs):
        super().__init__(**kwargs)
        self.service_id: str = service_id

    @property
    def thread_pool(self) -> ThreadPoolExecutor:
        return self._data.get("thread_pool")
