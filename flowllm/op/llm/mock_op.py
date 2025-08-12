import time

from loguru import logger

from flowllm.context.registry_context import register_op
from flowllm.op.llm.llm_base_op import BaseLLMOp


@register_op()
class Mock1Op(BaseLLMOp):
    def execute(self):
        time.sleep(1)
        a: int = self.op_params["a"]
        b: str = self.op_params["b"]
        logger.info(f"enter class={self.name}. a={a} b={b}")


@register_op()
class Mock2Op(Mock1Op):
    ...


@register_op()
class Mock3Op(Mock1Op):
    ...


@register_op()
class Mock4Op(Mock1Op):
    ...


@register_op()
class Mock5Op(Mock1Op):
    ...


@register_op()
class Mock6Op(Mock1Op):
    ...
