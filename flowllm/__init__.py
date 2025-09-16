import os

from flowllm.utils.common_utils import load_env

load_env()

assert "FLOW_APP_NAME" in os.environ, "please set FLOW_APP_NAME in `.env`!"

__version__ = "0.1.10"

from flowllm.app import FlowLLMApp
from flowllm.op import BaseOp, BaseAsyncOp, BaseAsyncToolOp, BaseMcpOp
from flowllm.context.service_context import C
