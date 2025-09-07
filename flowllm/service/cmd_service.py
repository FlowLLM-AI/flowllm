from loguru import logger

from flowllm.context.service_context import C
from flowllm.flow.gallery import CmdFlow
from flowllm.service.base_service import BaseService


@C.register_service("cmd")
class CmdService(BaseService):

    def integrate_flows(self):
        ...

    def execute(self):
        flow = CmdFlow(flow=self.service_config.cmd.flow)
        response = flow.sync_call(**self.service_config.cmd.params)
        if response.answer:
            logger.info(f"response.answer={response.answer}")
