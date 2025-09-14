from flowllm.op.base_async_op import BaseAsyncOp
from flowllm.op.base_op import BaseOp


class ParallelOp(BaseAsyncOp):

    def execute(self):
        for op in self.ops:
            assert not op.async_mode
            self.submit_task(op.call, context=self.context)
        self.join_task(task_desc="parallel execution")

    async def async_execute(self):
        for op in self.ops:
            assert op.async_mode
            assert isinstance(op, BaseAsyncOp)
            self.submit_async_task(op.async_call, context=self.context)
        return await self.join_async_task()

    def __or__(self, op: BaseOp):
        self.check_async(op)

        if isinstance(op, ParallelOp):
            self.ops.extend(op.ops)
        else:
            self.ops.append(op)
        return self
