import asyncio
import time

from loguru import logger

from flowllm.context import C
from flowllm.op.base_async_op import BaseAsyncOp
from flowllm.op.base_op import BaseOp


@C.register_op(register_app="FlowLLM")
class Mock1Op(BaseOp):
    def execute(self):
        time.sleep(1)
        a = self.context.get("a", 1)
        b = self.context.get("b", 2)
        logger.info(f"enter class={self.name}. a={a} b={b}")

        self.context.response.answer = f"{self.name} a={a} b={b} answer=47"


@C.register_op(register_app="FlowLLM")
class Mock2Op(Mock1Op):
    ...


@C.register_op(register_app="FlowLLM")
class Mock3Op(Mock1Op):
    ...


@C.register_op(register_app="FlowLLM")
class Mock4Op(BaseAsyncOp):
    async def async_execute(self):
        await asyncio.sleep(1)
        a = self.context.get("a", 1)
        b = self.context.get("b", 2)
        logger.info(f"enter class={self.name}. a={a} b={b}")
        self.context.response.answer = f"{self.name} a={a} b={b} answer=47"


@C.register_op(register_app="FlowLLM")
class Mock5Op(Mock4Op):
    ...


@C.register_op(register_app="FlowLLM")
class Mock6Op(Mock4Op):
    ...
