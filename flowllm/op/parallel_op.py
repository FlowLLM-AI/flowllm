from typing import List

from flowllm.op.base_op import BaseOp


class ParallelOp(BaseOp):

    def __init__(self, ops: List[BaseOp], **kwargs):
        super().__init__(**kwargs)
        self.ops = ops

    def execute(self):
        for op in self.ops:
            self.submit_task(op.__call__, context=self.context)
        self.join_task(task_desc="parallel execution")

    async def async_execute(self):
        for op in self.ops:
            self.submit_async_task(op.async_call, context=self.context)
        return await self.join_async_task()

    def __or__(self, op: BaseOp):
        if isinstance(op, ParallelOp):
            self.ops.extend(op.ops)
        else:
            self.ops.append(op)
        return self
