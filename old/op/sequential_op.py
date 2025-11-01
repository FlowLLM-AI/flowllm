from flowllm.op.base_async_op import BaseAsyncOp
from flowllm.op.base_op import BaseOp


class SequentialOp(BaseAsyncOp):
    """
    Composite operation that executes child operations sequentially.

    Created using the >> operator: op1 >> op2 >> op3

    Executes operations one after another, passing the same context through all operations.
    The context accumulates data as each operation runs, allowing later operations to use
    results from earlier ones.

    Supports both sync and async modes:
    - Sync mode: Calls op.call() for each operation
    - Async mode: Calls op.async_call() for each operation

    Returns the result from the last operation in the sequence.
    """

    def execute(self):
        """
        Execute operations sequentially in sync mode.

        Returns:
            Result from the last operation
        """
        result = None
        for op in self.ops:
            assert op.async_mode is False
            result = op.call(context=self.context)
        return result

    async def async_execute(self):
        """
        Execute operations sequentially in async mode.

        Returns:
            Result from the last operation
        """
        result = None
        for op in self.ops:
            assert op.async_mode is True
            assert isinstance(op, BaseAsyncOp)
            result = await op.async_call(context=self.context)
        return result

    def __rshift__(self, op: BaseOp):
        """
        Extend the sequence with another operation using >> operator.

        Args:
            op: Operation to append (can be another SequentialOp)

        Returns:
            Self with extended operation list
        """
        if isinstance(op, SequentialOp):
            self.ops.extend(op.ops)
        else:
            self.ops.append(op)
        return self

    def __lshift__(self, op: "BaseOp"):
        """Disallow << operator for sequential operations."""
        raise RuntimeError(f"`<<` is not supported in {self.name}")
