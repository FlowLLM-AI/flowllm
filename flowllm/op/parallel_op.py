from flowllm.op.base_async_op import BaseAsyncOp
from flowllm.op.base_op import BaseOp


class ParallelOp(BaseAsyncOp):
    """
    Composite operation that executes child operations in parallel.
    
    Created using the | operator: op1 | op2 | op3
    
    Executes all operations concurrently, each receiving the same initial context.
    Operations run independently and cannot access each other's results during execution.
    
    Supports both sync and async modes:
    - Sync mode: Uses thread pool to run operations in parallel
    - Async mode: Uses asyncio tasks for concurrent execution
    
    Returns:
        List of results from all operations (order may vary)
    """

    def execute(self):
        """
        Execute operations in parallel using thread pool (sync mode).
        
        Returns:
            List of all operation results
        """
        for op in self.ops:
            assert not op.async_mode
            self.submit_task(op.call, context=self.context)
        return self.join_task(task_desc="parallel execution")

    async def async_execute(self):
        """
        Execute operations in parallel using asyncio tasks (async mode).
        
        Returns:
            List of all operation results
        """
        for op in self.ops:
            assert op.async_mode
            assert isinstance(op, BaseAsyncOp)
            self.submit_async_task(op.async_call, context=self.context)
        return await self.join_async_task()

    def __or__(self, op: BaseOp):
        """
        Extend the parallel group with another operation using | operator.
        
        Args:
            op: Operation to add (can be another ParallelOp)
            
        Returns:
            Self with extended operation list
        """
        self.check_async(op)

        if isinstance(op, ParallelOp):
            self.ops.extend(op.ops)
        else:
            self.ops.append(op)
        return self

    def __lshift__(self, op: "BaseOp"):
        """Disallow << operator for parallel operations."""
        raise RuntimeError(f"`<<` is not supported in {self.name}")