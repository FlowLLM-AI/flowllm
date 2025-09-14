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

    async def async_call(self, context: FlowContext = None) -> Any:
        self.context = context
        with self.timer:
            if self.max_retries == 1 and self.raise_exception:
                await self.async_before_execute()
                await self.async_execute()
                await self.async_after_execute()

            else:
                for i in range(self.max_retries):
                    try:
                        await self.async_before_execute()
                        await self.async_execute()
                        await self.async_after_execute()
                        break

                    except Exception as e:
                        logger.exception(f"op={self.name} async execute failed, error={e.args}")

                        if i == self.max_retries:
                            if self.raise_exception:
                                raise e
                            else:
                                await self.async_default_execute()

        if self.context is not None and self.context.response is not None:
            return self.context.response
        return None

    def submit_async_task(self, fn: Callable, *args, **kwargs):
        loop = asyncio.get_running_loop()
        if asyncio.iscoroutinefunction(fn):
            self.task_list.append(loop.create_task(fn(*args, **kwargs)))
        else:
            logger.warning("submit_async_task failed, fn is not a coroutine function!")

    async def join_async_task(self):
        result = []
        for t_result in await asyncio.gather(*self.task_list):
            if t_result:
                if isinstance(t_result, list):
                    result.extend(t_result)
                else:
                    result.append(t_result)

        self.task_list.clear()
        return result
