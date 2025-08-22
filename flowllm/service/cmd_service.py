from flowllm.context.service_context import C
from flowllm.flow.gallery import CmdFlow
from flowllm.service.base_service import BaseService


@C.register_service("cmd")
class CmdService(BaseService):

    def __call__(self):
        flow = CmdFlow(flow=self.service_config.cmd.flow)
        flow.__call__(**self.service_config.cmd.params)
