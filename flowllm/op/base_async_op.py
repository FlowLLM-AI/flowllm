import asyncio
from abc import ABCMeta
from typing import Any, Callable

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.op.base_op import BaseOp


class BaseAsyncOp(BaseOp, metaclass=ABCMeta):

    def __init__(self, **kwargs):
        if "async_mode" not in kwargs:
            kwargs["async_mode"] = True
        super().__init__(**kwargs)

    async def async_before_execute(self):
        ...

    async def async_after_execute(self):
        ...

    async def async_execute(self):
        ...

    async def async_default_execute(self):
        ...

    async def async_call(self, context: FlowContext = None, **kwargs) -> Any:
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
        loop = asyncio.get_running_loop()
        if asyncio.iscoroutinefunction(fn):
            task = loop.create_task(fn(*args, **kwargs))
            self.task_list.append(task)
        else:
            logger.warning("submit_async_task failed, fn is not a coroutine function!")

    async def join_async_task(self, timeout: float = None, return_exceptions: bool = True):
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
