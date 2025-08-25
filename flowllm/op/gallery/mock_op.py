import time

from loguru import logger

from flowllm.context.service_context import C
from flowllm.op.base_llm_op import BaseLLMOp


@C.register_op()
class Mock1Op(BaseLLMOp):
    def execute(self):
        time.sleep(1)
        a = self.context.a
        b = self.context.b
        logger.info(f"enter class={self.name}. a={a} b={b}")

        self.context.response.answer = f"{self.name} {a} {b} answer=47"


@C.register_op()
class Mock2Op(Mock1Op):
    ...


@C.register_op()
class Mock3Op(Mock1Op):
    ...


@C.register_op()
class Mock4Op(Mock1Op):
    ...


@C.register_op()
class Mock5Op(Mock1Op):
    ...


@C.register_op()
class Mock6Op(Mock1Op):
    ...
