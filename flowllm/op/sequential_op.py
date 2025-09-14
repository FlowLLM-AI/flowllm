from flowllm.op.base_async_op import BaseAsyncOp
from flowllm.op.base_op import BaseOp


class SequentialOp(BaseAsyncOp):

    def execute(self):
        for op in self.ops:
            assert op.async_mode is False
            op.call(self.context)

    async def async_execute(self):
        for op in self.ops:
            assert op.async_mode is True
            assert isinstance(op, BaseAsyncOp)
            await op.async_call(self.context)

    def __rshift__(self, op: BaseOp):
        if isinstance(op, SequentialOp):
            self.ops.extend(op.ops)
        else:
            self.ops.append(op)
        return self
