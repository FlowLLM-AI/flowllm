from typing import List

from v2.op.base_op import BaseOp


class ParallelOp(BaseOp):
    """Container class for parallel operation execution

    Executes multiple operations in parallel, all operations use the same input,
    returns a list of results from all operations.
    Supports parallel calls: op1 | op2 | op3
    Falls back to sequential execution if no thread pool is available.
    """

    def __init__(self, ops: List[BaseOp], **kwargs):
        super().__init__(**kwargs)
        self.ops = ops

    def execute(self):
        for op in self.ops:
            self.submit_task(op.__call__)

        return self.join_task(task_desc="Parallel execution")

    def __or__(self, op: BaseOp):
        if isinstance(op, ParallelOp):
            self.ops.extend(op.ops)
        else:
            self.ops.append(op)
        return self
