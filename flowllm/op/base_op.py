import asyncio
from abc import ABC
from concurrent.futures import Future
from typing import List, Any, Optional, Callable

from loguru import logger
from tqdm import tqdm

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.utils.common_utils import camel_to_snake
from flowllm.utils.timer import Timer


class BaseOp(ABC):

    def __init__(self,
                 name: str = "",
                 max_retries: int = 1,
                 raise_exception: bool = True,
                 enable_multithread: bool = True,
                 **kwargs):
        super().__init__()

        self.name: str = name or camel_to_snake(self.__class__.__name__)
        self.max_retries: int = max_retries
        self.raise_exception: bool = raise_exception
        self.enable_multithread: bool = enable_multithread
        self.op_params: dict = kwargs

        self.task_list: List[Future] = []
        self.async_task_list: List = []
        self.ray_task_list: List = []
        self.timer = Timer(name=self.name)
        self.context: FlowContext | None = None
        self.sub_op: Optional["BaseOp"] = None

    def before_execute(self):
        ...

    def after_execute(self):
        ...

    def execute(self):
        ...

    def default_execute(self):
        ...

    async def async_execute(self):
        ...

    def __call__(self, context: FlowContext = None):
        self.context = context
        with self.timer:
            if self.max_retries == 1 and self.raise_exception:
                self.before_execute()
                self.execute()
                self.after_execute()

            else:
                for i in range(self.max_retries):
                    try:
                        self.before_execute()
                        self.execute()
                        self.after_execute()

                    except Exception as e:
                        logger.exception(f"op={self.name} execute failed, error={e.args}")

                        if i == self.max_retries - 1:
                            if self.raise_exception:
                                raise e
                            else:
                                self.default_execute()

        if self.context is not None and self.context.response is not None:
            return self.context.response
        return None

    async def async_call(self, context: FlowContext = None) -> Any:
        self.context = context
        with self.timer:
            if self.max_retries == 1 and self.raise_exception:
                self.before_execute()
                await self.async_execute()
                self.after_execute()

            else:
                for i in range(self.max_retries):
                    try:
                        self.before_execute()
                        await self.async_execute()
                        self.after_execute()

                    except Exception as e:
                        logger.exception(f"op={self.name} async execute failed, error={e.args}")

                        if i == self.max_retries:
                            if self.raise_exception:
                                raise e
                            else:
                                self.default_execute()

        if self.context is not None and self.context.response is not None:
            return self.context.response
        return None

    def submit_async_task(self, fn: Callable, *args, **kwargs):
        if asyncio.iscoroutinefunction(fn):
            task = asyncio.create_task(fn(*args, **kwargs))
            self.async_task_list.append(task)
        else:
            logger.warning("submit_async_task failed, fn is not a coroutine function!")

    async def join_async_task(self):
        result = []
        for task in self.async_task_list:
            t_result = await task
            if t_result:
                if isinstance(t_result, list):
                    result.extend(t_result)
                else:
                    result.append(t_result)

        self.async_task_list.clear()
        return result

    def submit_task(self, fn, *args, **kwargs):
        if self.enable_multithread:
            task = C.thread_pool.submit(fn, *args, **kwargs)
            self.task_list.append(task)

        else:
            result = fn(*args, **kwargs)
            if result:
                if isinstance(result, list):
                    result.extend(result)
                else:
                    result.append(result)

        return self

    def join_task(self, task_desc: str = None) -> list:
        result = []
        if self.enable_multithread:
            for task in tqdm(self.task_list, desc=task_desc or self.name):
                t_result = task.result()
                if t_result:
                    if isinstance(t_result, list):
                        result.extend(t_result)
                    else:
                        result.append(t_result)

        else:
            result.extend(self.task_list)

        self.task_list.clear()
        return result

    def __rshift__(self, op: "BaseOp"):
        from flowllm.op.sequential_op import SequentialOp

        sequential_op = SequentialOp(ops=[self])

        if isinstance(op, SequentialOp):
            sequential_op.ops.extend(op.ops)
        else:
            sequential_op.ops.append(op)
        return sequential_op

    def __lshift__(self, op: "BaseOp"):
        self.sub_op = op

    def __or__(self, op: "BaseOp"):
        from flowllm.op.parallel_op import ParallelOp

        parallel_op = ParallelOp(ops=[self])

        if isinstance(op, ParallelOp):
            parallel_op.ops.extend(op.ops)
        else:
            parallel_op.ops.append(op)

        return parallel_op


def run1():
    """Basic test"""

    class MockOp(BaseOp):
        def execute(self):
            logger.info(f"op={self.name} execute")

        async def async_execute(self):
            logger.info(f"op={self.name} async_execute")

    mock_op = MockOp()
    mock_op()


def run2():
    """Test operator overloading functionality"""
    from concurrent.futures import ThreadPoolExecutor
    import time

    class TestOp(BaseOp):

        def execute(self):
            time.sleep(0.1)
            op_result = f"{self.name}"
            logger.info(f"Executing {op_result}")
            return op_result

        async def async_execute(self):
            await asyncio.sleep(0.1)
            op_result = f"{self.name}"
            logger.info(f"Async executing {op_result}")
            return op_result

    # Create service_context for parallel execution
    C["thread_pool"] = ThreadPoolExecutor(max_workers=4)

    # Create test operations
    op1 = TestOp("op1")
    op2 = TestOp("op2")
    op3 = TestOp("op3")
    op4 = TestOp("op4")

    logger.info("=== Testing sequential execution op1 >> op2 ===")
    sequential = op1 >> op2
    result = sequential()
    logger.info(f"Sequential result: {result}")

    logger.info("=== Testing parallel execution op1 | op2 ===")
    parallel = op1 | op2
    result = parallel()
    logger.info(f"Parallel result: {result}")


async def async_run1():
    """Basic async test"""

    class MockOp(BaseOp):
        def execute(self):
            logger.info(f"op={self.name} execute")

        async def async_execute(self):
            logger.info(f"op={self.name} async_execute")

    mock_op = MockOp()
    await mock_op.async_call()


async def async_run2():
    """Test async operator overloading functionality"""
    from concurrent.futures import ThreadPoolExecutor
    import time

    class TestOp(BaseOp):

        def execute(self):
            time.sleep(0.1)
            op_result = f"{self.name}"
            logger.info(f"Executing {op_result}")
            return op_result

        async def async_execute(self):
            await asyncio.sleep(0.1)
            op_result = f"{self.name}"
            logger.info(f"Async executing {op_result}")
            return op_result

    # Create service_context for parallel execution
    C["thread_pool"] = ThreadPoolExecutor(max_workers=4)

    # Create test operations
    op1 = TestOp("op1")
    op2 = TestOp("op2")
    op3 = TestOp("op3")
    op4 = TestOp("op4")

    logger.info("=== Testing async sequential execution op1 >> op2 ===")
    sequential = op1 >> op2
    result = await sequential.async_call()
    logger.info(f"Async sequential result: {result}")

    logger.info("=== Testing async parallel execution op1 | op2 ===")
    parallel = op1 | op2
    result = await parallel.async_call()
    logger.info(f"Async parallel result: {result}")

    logger.info("=== Testing async mixed calls op1 >> (op2 | op3) >> op4 ===")
    mixed = op1 >> (op2 | op3) >> op4
    result = await mixed.async_call()
    logger.info(f"Async mixed result: {result}")

    logger.info("=== Testing async complex mixed calls op1 >> (op1 | (op2 >> op3)) >> op4 ===")
    complex_mixed = op1 >> (op1 | (op2 >> op3)) >> op4
    result = await complex_mixed.async_call()
    logger.info(f"Async complex mixed result: {result}")

if __name__ == "__main__":
    run1()
    print("\n" + "=" * 50 + "\n")
    run2()

    print("\n" + "=" * 50 + "\n")
    print("Running async tests:")


    async def main():
        await async_run1()
        print("\n" + "=" * 50 + "\n")
        await async_run2()


    asyncio.run(main())
