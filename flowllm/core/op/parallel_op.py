"""Parallel operation execution.

This module provides the ParallelOp class, which executes operations
in parallel, collecting all results at the end.
"""

from typing import Union

from .base_async_op import BaseAsyncOp
from .base_op import BaseOp


class ParallelOp(BaseAsyncOp):
    """Operation that executes sub-operations in parallel.

    This operation executes all sub-operations concurrently and collects
    their results. All operations receive the same context.

    Example:
        ```python
        op1 = MyOp1()
        op2 = MyOp2()
        parallel = op1 | op2  # Creates ParallelOp
        results = parallel.call(context=FlowContext())
        ```
    """

    def execute(self):
        """Execute operations in parallel in sync mode.

        Uses multithreading to execute operations concurrently.

        Returns:
            List of results from all operations
        """
        for op in self.ops:
            assert not op.async_mode
            self.submit_task(op.call, context=self.context)
        return self.join_task(task_desc="parallel execution")

    async def async_execute(self):
        """Execute operations in parallel in async mode.

        Uses asyncio tasks to execute operations concurrently.

        Returns:
            List of results from all operations
        """
        for op in self.ops:
            assert op.async_mode
            assert isinstance(op, BaseAsyncOp)
            self.submit_async_task(op.async_call, context=self.context)
        return await self.join_async_task()

    def __lshift__(self, op: Union["BaseOp", dict, list]):
        """Left shift operator is not supported in ParallelOp.

        Args:
            op: Operation (not used)

        Raises:
            RuntimeError: Always raises, as `<<` is not supported
        """
        raise RuntimeError(f"`<<` is not supported in {self.name}")

    def __or__(self, op: BaseOp):
        """Bitwise OR operator for adding operations to parallel execution.

        Args:
            op: Operation to run in parallel

        Returns:
            Self with the operation added to parallel execution
        """
        self.check_async(op)

        if isinstance(op, ParallelOp):
            self.ops.extend(op.ops)
        else:
            self.ops.append(op)
        return self
