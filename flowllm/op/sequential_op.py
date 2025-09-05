from typing import List

from flowllm.op.base_op import BaseOp


class SequentialOp(BaseOp):

    def __init__(self, ops: List[BaseOp], **kwargs):
        super().__init__(**kwargs)
        self.ops = ops

    def execute(self):
        for op in self.ops:
            op.__call__(self.context)

    async def async_execute(self):
        for op in self.ops:
            await op.async_call(self.context)

    def __rshift__(self, op: BaseOp):
        if isinstance(op, SequentialOp):
            self.ops.extend(op.ops)
        else:
            self.ops.append(op)
        return self
