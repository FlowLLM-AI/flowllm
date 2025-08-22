from abc import abstractmethod, ABC
from concurrent.futures import Future
from typing import List

from loguru import logger
from tqdm import tqdm

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.utils.common_utils import camel_to_snake
from flowllm.utils.timer import Timer


class BaseOp(ABC):

    def __init__(self,
                 name: str = "",
                 raise_exception: bool = True,
                 **kwargs):
        super().__init__()

        self.name: str = name or camel_to_snake(self.__class__.__name__)
        self.raise_exception: bool = raise_exception
        self.op_params: dict = kwargs

        self.task_list: List[Future] = []
        self.timer = Timer(name=self.name)
        self.context: FlowContext | None = None

    @abstractmethod
    def execute(self):
        ...

    def __call__(self, context: FlowContext = None):
        self.context = context
        with self.timer:
            if self.raise_exception:
                self.execute()

            else:

                try:
                    self.execute()
                except Exception as e:
                    logger.exception(f"op={self.name} execute failed, error={e.args}")

        return self.context.response if self.context else None

    def submit_task(self, fn, *args, **kwargs):
        task = C.thread_pool.submit(fn, *args, **kwargs)
        self.task_list.append(task)
        return self

    def join_task(self, task_desc: str = None) -> list:
        result = []
        for task in tqdm(self.task_list, desc=task_desc or self.name):
            t_result = task.result()
            if t_result:
                if isinstance(t_result, list):
                    result.extend(t_result)
                else:
                    result.append(t_result)
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

    logger.info("=== Testing mixed calls op1 >> (op2 | op3) >> op4 ===")
    mixed = op1 >> (op2 | op3) >> op4
    result = mixed()
    logger.info(f"Mixed result: {result}")

    logger.info("=== Testing complex mixed calls op1 >> (op1 | (op2 >> op3)) >> op4 ===")
    complex_mixed = op1 >> (op1 | (op2 >> op3)) >> op4
    result = complex_mixed()
    logger.info(f"Complex mixed result: {result}")


if __name__ == "__main__":
    run1()
    print("\n" + "=" * 50 + "\n")
    run2()
