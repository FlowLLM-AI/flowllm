from abc import abstractmethod, ABC
from concurrent.futures import Future
from typing import List

import ray
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
        self.ray_task_list: List = []  # Ray ObjectRef list
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

    def submit_ray_task(self, fn, *args, **kwargs):
        if C.service_config.ray_max_workers <= 1:
            raise RuntimeError("Ray is not configured. Please set ray_max_workers > 1 in service config.")
        
        if not ray.is_initialized():
            logger.warning(f"Ray is not initialized. Initializing Ray with {C.service_config.ray_max_workers} workers.")
            ray.init(num_cpus=C.service_config.ray_max_workers)

        remote_fn = ray.remote(fn)
        task = remote_fn.remote(*args, **kwargs)
        self.ray_task_list.append(task)
        return self

    def join_ray_task(self, task_desc: str = None) -> list:
        result = []
        for task in tqdm(self.ray_task_list, desc=task_desc or f"{self.name}_ray"):
            t_result = ray.get(task)
            if t_result:
                if isinstance(t_result, list):
                    result.extend(t_result)
                else:
                    result.append(t_result)
        self.ray_task_list.clear()
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


def run3():
    """Test Ray multiprocessing functionality"""
    import time
    import math

    # CPU intensive task for testing
    def cpu_intensive_task(n: int, task_id: str):
        """CPU intensive task: calculate prime numbers"""
        start_t = time.time()

        def is_prime(num):
            if num < 2:
                return False
            for j in range(2, int(math.sqrt(num)) + 1):
                if num % j == 0:
                    return False
            return True

        primes = [x for x in range(2, n) if is_prime(x)]
        end_t = time.time()

        result = {
            'task_id': task_id,
            'prime_count': len(primes),
            'max_prime': max(primes) if primes else 0,
            'execution_time': end_t - start_t
        }
        logger.info(f"Task {task_id} completed: found {len(primes)} primes, time: {result['execution_time']:.2f}s")
        return result

    class TestRayOp(BaseOp):
        def execute(self):
            logger.info(f"Executing {self.name}")
            return f"Result from {self.name}"

    # Initialize service config for Ray
    from flowllm.schema.service_config import ServiceConfig

    # Create a test service config with Ray enabled
    test_config = ServiceConfig()
    test_config.ray_max_workers = 4  # Enable Ray with 4 workers
    test_config.thread_pool_max_workers = 4

    # Set the service config
    C.init_by_service_config(test_config)

    logger.info("=== Testing Ray multiprocessing ===")

    # Create test operation
    ray_op = TestRayOp("ray_test_op")

    logger.info("--- Testing submit_ray_task and join_ray_task ---")

    # Test 1: Basic Ray task submission
    task_size = 50000  # Find primes up to 50000 (more CPU intensive)
    num_tasks = 4

    try:
        # Submit multiple CPU-intensive tasks

        logger.info(f"Submitting {num_tasks} Ray tasks (finding primes up to {task_size})")
        start_time = time.time()

        for i in range(num_tasks):
            ray_op.submit_ray_task(cpu_intensive_task, task_size, f"ray_task_{i}")

        # Wait for all tasks to complete
        results = ray_op.join_ray_task("Processing Ray tasks")
        end_time = time.time()

        logger.info(f"Ray tasks completed in {end_time - start_time:.2f}s")
        logger.info(f"Ray results: {results}")

    except Exception as e:
        logger.error(f"Ray task execution failed: {e}")

    # Test 2: Compare Ray vs ThreadPool performance
    logger.info("\n--- Performance Comparison: Ray vs ThreadPool ---")

    try:
        # Test with ThreadPool
        thread_op = TestRayOp("thread_test_op")

        logger.info(f"Testing ThreadPool with {num_tasks} tasks")
        start_time = time.time()

        for i in range(num_tasks):
            thread_op.submit_task(cpu_intensive_task, task_size, f"thread_task_{i}")

        thread_results = thread_op.join_task("Processing ThreadPool tasks")
        print(thread_results)
        thread_time = time.time() - start_time

        logger.info(f"ThreadPool completed in {thread_time:.2f}s")

        # Test with Ray again for comparison
        ray_op2 = TestRayOp("ray_test_op2")

        logger.info(f"Testing Ray with {num_tasks} tasks")
        start_time = time.time()

        for i in range(num_tasks):
            ray_op2.submit_ray_task(cpu_intensive_task, task_size, f"ray_task2_{i}")

        ray_results2 = ray_op2.join_ray_task("Processing Ray tasks (comparison)")
        print(ray_results2)
        ray_time = time.time() - start_time

        logger.info(f"Ray completed in {ray_time:.2f}s")

        # Performance comparison
        speedup = thread_time / ray_time if ray_time > 0 else 0
        logger.info(f"\n=== Performance Summary ===")
        logger.info(f"ThreadPool time: {thread_time:.2f}s")
        logger.info(f"Ray time: {ray_time:.2f}s")
        logger.info(f"Ray speedup: {speedup:.2f}x")

    except Exception as e:
        logger.error(f"Performance comparison failed: {e}")

    # Test 3: Error handling
    logger.info("\n--- Testing Error Handling ---")

    def failing_task(task_id: str):
        if task_id == "fail_task":
            raise ValueError(f"Intentional error in {task_id}")
        return f"Success: {task_id}"

    try:
        error_op = TestRayOp("error_test_op")

        # Submit mix of successful and failing tasks
        error_op.submit_ray_task(failing_task, "success_task_1")
        error_op.submit_ray_task(failing_task, "fail_task")
        error_op.submit_ray_task(failing_task, "success_task_2")

        error_results = error_op.join_ray_task("Testing error handling")
        logger.info(f"Error handling results: {error_results}")

    except Exception as e:
        logger.error(f"Expected error occurred: {e}")

    # Test 4: Ray without proper configuration (should fail)
    logger.info("\n--- Testing Ray Configuration Validation ---")

    original_workers = C.service_config.ray_max_workers
    try:
        # Temporarily disable Ray in config
        C.service_config.ray_max_workers = 1  # Disable Ray

        config_test_op = TestRayOp("config_test_op")
        config_test_op.submit_ray_task(cpu_intensive_task, 100, "config_test")

        logger.error("This should not be reached - Ray should be disabled")

    except RuntimeError as e:
        logger.info(f"✓ Correctly caught configuration error: {e}")

    finally:
        # Restore original configuration
        C.service_config.ray_max_workers = original_workers

    logger.info("\n=== Ray testing completed ===")


if __name__ == "__main__":
    run1()
    print("\n" + "=" * 50 + "\n")
    run2()
    print("\n" + "=" * 50 + "\n")
    run3()
