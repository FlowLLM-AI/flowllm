import asyncio
from abc import ABCMeta
from typing import Any, Callable

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.op.base_op import BaseOp


class BaseAsyncOp(BaseOp, metaclass=ABCMeta):
    """
    Base class for asynchronous operations.

    Extends BaseOp with async/await support for non-blocking execution.
    Provides async versions of all execution hooks and async task management.

    Key features:
    - Async execution with retry logic
    - Non-blocking task submission and gathering
    - Timeout support for async operations
    - Automatic task cleanup on errors
    """

    def __init__(self, **kwargs):
        """Initialize async operation with async_mode=True by default."""
        if "async_mode" not in kwargs:
            kwargs["async_mode"] = True
        super().__init__(**kwargs)

    async def async_before_execute(self):
        """Async hook called before async_execute(). Override to add pre-execution logic."""
        ...

    async def async_after_execute(self):
        """Async hook called after async_execute(). Override to add post-execution logic."""
        ...

    async def async_execute(self):
        """Main async execution logic. Override this method in subclasses."""
        ...

    async def async_default_execute(self):
        """Fallback async execution when all retries fail. Override for default behavior."""
        ...

    async def async_call(self, context: FlowContext = None, **kwargs) -> Any:
        """
        Execute the operation asynchronously with retry logic and error handling.

        This is the main entry point for async operations. It:
        1. Builds/updates the context with provided parameters
        2. Tracks execution time
        3. Executes the operation with retry logic
        4. Returns result, context.response, or None

        Args:
            context: Execution context to pass data between operations
            **kwargs: Additional parameters added to context

        Returns:
            Operation result, context.response, or None
        """
        self.context = self.build_context(context, **kwargs)
        with self.timer:
            result = None
            if self.max_retries == 1 and self.raise_exception:
                await self.async_before_execute()
                result = await self.async_execute()
                await self.async_after_execute()

            else:
                for i in range(self.max_retries):
                    try:
                        await self.async_before_execute()
                        result = await self.async_execute()
                        await self.async_after_execute()
                        break

                    except Exception as e:
                        logger.exception(f"op={self.name} async execute failed, error={e.args}")

                        if i == self.max_retries - 1:
                            if self.raise_exception:
                                raise e
                            else:
                                result = await self.async_default_execute()

        if result is not None:
            return result
        elif self.context is not None and self.context.response is not None:
            return self.context.response
        else:
            return None

    def submit_async_task(self, fn: Callable, *args, **kwargs):
        """
        Submit an async coroutine for concurrent execution.

        Creates an asyncio task that will run concurrently with other tasks.
        Only accepts coroutine functions (async def).

        Args:
            fn: Async function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
        """
        loop = asyncio.get_running_loop()
        if asyncio.iscoroutinefunction(fn):
            task = loop.create_task(fn(*args, **kwargs))
            self.task_list.append(task)
        else:
            logger.warning("submit_async_task failed, fn is not a coroutine function!")

    async def join_async_task(self, timeout: float = None, return_exceptions: bool = True):
        """
        Wait for all submitted async tasks to complete and collect results.

        Features:
        - Optional timeout with automatic task cancellation
        - Exception handling with optional exception collection
        - Automatic task cleanup on timeout or error

        Args:
            timeout: Maximum time to wait in seconds (None for no timeout)
            return_exceptions: If True, exceptions are returned as results instead of raising

        Returns:
            Combined list of all task results (excluding exceptions if return_exceptions=True)

        Raises:
            asyncio.TimeoutError: If timeout is exceeded
            Exception: Any exception from tasks if return_exceptions=False
        """
        result = []

        if not self.task_list:
            return result

        try:
            if timeout is not None:
                gather_task = asyncio.gather(*self.task_list, return_exceptions=return_exceptions)
                task_results = await asyncio.wait_for(gather_task, timeout=timeout)
            else:
                task_results = await asyncio.gather(*self.task_list, return_exceptions=return_exceptions)

            for t_result in task_results:
                if return_exceptions and isinstance(t_result, Exception):
                    logger.exception(f"Task failed with exception", exc_info=t_result)
                    continue

                if t_result:
                    if isinstance(t_result, list):
                        result.extend(t_result)
                    else:
                        result.append(t_result)

        except asyncio.TimeoutError as e:
            logger.exception(f"join_async_task timeout after {timeout}s, cancelling {len(self.task_list)} tasks...")
            for task in self.task_list:
                if not task.done():
                    task.cancel()

            await asyncio.gather(*self.task_list, return_exceptions=True)
            self.task_list.clear()
            raise

        except Exception as e:
            logger.exception(f"join_async_task failed with {type(e).__name__}, cancelling remaining tasks...")
            for task in self.task_list:
                if not task.done():
                    task.cancel()

            await asyncio.gather(*self.task_list, return_exceptions=True)
            self.task_list.clear()
            raise

        finally:
            self.task_list.clear()

        return result
