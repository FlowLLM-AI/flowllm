from flowllm.op.base_async_op import BaseAsyncOp
from flowllm.op.base_op import BaseOp


class SequentialOp(BaseAsyncOp):

    def execute(self):
        result = None
        for op in self.ops:
            assert op.async_mode is False
            result = op.call(context=self.context)
        return result

    async def async_execute(self):
        result = None
        for op in self.ops:
            assert op.async_mode is True
            assert isinstance(op, BaseAsyncOp)
            result = await op.async_call(context=self.context)
        return result

    def __rshift__(self, op: BaseOp):
        if isinstance(op, SequentialOp):
            self.ops.extend(op.ops)
        else:
            self.ops.append(op)
        return self

    def __lshift__(self, op: "BaseOp"):
        raise RuntimeError(f"`<<` is not supported in {self.name}")