from typing import List

from v2.op.base_op import BaseOp


class SequentialOp(BaseOp):
    """Container class for sequential operation execution

    Executes multiple operations in sequence, where the output of the previous operation
    becomes the input of the next operation.
    Supports chaining: op1 >> op2 >> op3
    """

    def __init__(self, ops: List[BaseOp], **kwargs):
        super().__init__(**kwargs)
        self.ops = ops

    def execute(self):
        result = None
        for op in self.ops:
            result = op.execute()
        return result

    def __rshift__(self, op: BaseOp):
        if isinstance(op, SequentialOp):
            self.ops.extend(op.ops)
        else:
            self.ops.append(op)
        return self
