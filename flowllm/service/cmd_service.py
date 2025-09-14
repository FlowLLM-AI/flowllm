from loguru import logger

from flowllm.context.service_context import C
from flowllm.flow.cmd_flow import CmdFlow
from flowllm.service.base_service import BaseService


@C.register_service("cmd")
class CmdService(BaseService):

    def run(self):
        super().run()
        cmd_config = self.service_config.cmd
        flow = CmdFlow(flow=cmd_config.flow)
        response = flow.call(**self.service_config.cmd.params)
        if response.answer:
            logger.info(f"response.answer={response.answer}")
