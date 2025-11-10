"""Sequential operation execution.

This module provides the SequentialOp class, which executes operations
sequentially one after another, passing the context through the chain.
"""

from typing import Union

from .base_async_op import BaseAsyncOp
from .base_op import BaseOp


class SequentialOp(BaseAsyncOp):
    """Operation that executes sub-operations sequentially.

    This operation executes its sub-operations in order, passing the context
    from one operation to the next. Each operation receives the output context
    from the previous operation.

    Example:
        ```python
        op1 = MyOp1()
        op2 = MyOp2()
        sequential = op1 >> op2  # Creates SequentialOp
        result = sequential.call(context=FlowContext())
        ```
    """

    def execute(self):
        """Execute operations sequentially in sync mode.

        Returns:
            Result from the last operation in the sequence
        """
        result = None
        for op in self.ops:
            assert op.async_mode is False
            result = op.call(context=self.context)
        return result

    async def async_execute(self):
        """Execute operations sequentially in async mode.

        Returns:
            Result from the last operation in the sequence
        """
        result = None
        for op in self.ops:
            assert op.async_mode is True
            assert isinstance(op, BaseAsyncOp)
            result = await op.async_call(context=self.context)
        return result

    def __lshift__(self, op: Union["BaseOp", dict, list]):
        """Left shift operator is not supported in SequentialOp.

        Args:
            op: Operation (not used)

        Raises:
            RuntimeError: Always raises, as `<<` is not supported
        """
        raise RuntimeError(f"`<<` is not supported in {self.name}")

    def __rshift__(self, op: BaseOp):
        """Right shift operator for chaining operations sequentially.

        Args:
            op: Operation to chain sequentially

        Returns:
            Self with the operation added to the sequence
        """
        if isinstance(op, SequentialOp):
            self.ops.extend(op.ops)
        else:
            self.ops.append(op)
        return self
