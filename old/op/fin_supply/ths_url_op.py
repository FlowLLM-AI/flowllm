from loguru import logger

from flowllm.context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_async_op import BaseAsyncOp


@C.register_op(register_app="FlowLLM")
class ThsUrlOp(BaseAsyncOp):

    def __init__(self, url_template: str = "", **kwargs):
        super().__init__(**kwargs)
        self.url_template: str = url_template

    async def async_execute(self):
        code: str = self.context.code
        self.context.url = self.url_template.format(code=code)
        logger.info(f"{self.name} url={self.context.url}")


async def main():
    op = ThsUrlOp(url_template="http://aaa/{code}/bbb")
    await op.async_call(context=FlowContext(code="123456"))
    print(op.context)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
