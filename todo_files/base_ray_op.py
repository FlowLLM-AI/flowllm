from abc import ABC

import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.context.service_context import C
from flowllm.op.base_op import BaseOp


class BaseRayOp(BaseOp, ABC):
    """
    Base class for Ray-based operations that provides parallel task execution capabilities.
    Inherits from BaseOp and provides methods for submitting and joining Ray tasks.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ray_task_list = []

    def submit_and_join_ray_task(self, fn, parallel_key: str = "", task_desc: str = "",
                                 enable_test: bool = False, **kwargs):
        """
        Submit multiple Ray tasks in parallel and wait for all results.
        
        This method automatically detects a list parameter to parallelize over, distributes
        the work across multiple Ray workers, and returns the combined results.
        
        Args:
            fn: Function to execute in parallel
            parallel_key: Key of the parameter to parallelize over (auto-detected if empty)
            task_desc: Description for logging and progress bars
            enable_test: Enable test mode (prints results instead of executing)
            **kwargs: Arguments to pass to the function, including the list to parallelize over
        
        Returns:
            List of results from all parallel tasks
        """
        import ray
        max_workers = C.service_config.ray_max_workers
        self.ray_task_list.clear()

        # Auto-detect parallel key if not provided
        if not parallel_key:
            for key, value in kwargs.items():
                if isinstance(value, list):
                    parallel_key = key
                    logger.info(f"using first list parallel_key={parallel_key}")
                    break

        # Extract the list to parallelize over
        parallel_list = kwargs.pop(parallel_key)
        assert isinstance(parallel_list, list)

        # Convert pandas DataFrames to Ray objects for efficient sharing
        for key in sorted(kwargs.keys()):
            value = kwargs[key]
            if isinstance(value, pd.DataFrame):
                kwargs[key] = ray.put(value)

        if enable_test:
            test_result_list = []
            for value in parallel_list:
                kwargs.update({"actor_index": 0, parallel_key: value})
                t_result = fn(**kwargs)
                if t_result:
                    if isinstance(t_result, list):
                        test_result_list.extend(t_result)
                    else:
                        test_result_list.append(t_result)
            return test_result_list

        # Create and submit tasks for each worker
        for i in range(max_workers):
            def fn_wrapper():
                result_list = []
                # Distribute work using stride: worker i-th processes items [i, i+max_workers, i+2*max_workers, ...]
                for parallel_value in parallel_list[i::max_workers]:
                    kwargs.update({
                        "actor_index": i,
                        parallel_key: parallel_value,
                    })
                    part_result = fn(**kwargs)
                    if part_result:
                        if isinstance(part_result, list):
                            result_list.extend(part_result)
                        else:
                            result_list.append(part_result)
                return result_list

            self.submit_ray_task(fn=fn_wrapper)
            logger.info(f"ray.submit task_desc={task_desc} id={i}")

        # Wait for all tasks to complete and collect results
        result = self.join_ray_task(task_desc=task_desc)
        logger.info(f"{task_desc} complete. result_size={len(result)} resources={ray.available_resources()}")
        return result

    def submit_ray_task(self, fn, *args, **kwargs):
        """
        Submit a single Ray task for asynchronous execution.
        
        Args:
            fn: Function to execute remotely
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        
        Returns:
            Self for method chaining
        
        Raises:
            RuntimeError: If Ray is not configured (ray_max_workers <= 1)
        """
        import ray
        if C.service_config.ray_max_workers <= 1:
            raise RuntimeError("Ray is not configured. Please set ray_max_workers > 1 in service config.")

        # Initialize Ray if not already done
        if not ray.is_initialized():
            logger.warning(f"Ray is not initialized. Initializing Ray with {C.service_config.ray_max_workers} workers.")
            ray.init(num_cpus=C.service_config.ray_max_workers)

        # Create remote function and submit task
        remote_fn = ray.remote(fn)
        task = remote_fn.remote(*args, **kwargs)
        self.ray_task_list.append(task)
        return self

    def join_ray_task(self, task_desc: str = None) -> list:
        """
        Wait for all submitted Ray tasks to complete and collect their results.
        
        Args:
            task_desc: Description for the progress bar
            
        Returns:
            Combined list of results from all completed tasks
        """
        result = []
        # Process each task and collect results with progress bar
        import ray
        for task in tqdm(self.ray_task_list, desc=task_desc or f"{self.name}_ray"):
            t_result = ray.get(task)
            if t_result:
                if isinstance(t_result, list):
                    result.extend(t_result)
                else:
                    result.append(t_result)
        self.ray_task_list.clear()
        return result


def run():
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

    class TestRayOp(BaseRayOp):
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
    ray_op = TestRayOp(name="ray_test_op")

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
        thread_op = TestRayOp(name="thread_test_op")

        logger.info(f"Testing ThreadPool with {num_tasks} tasks")
        start_time = time.time()

        for i in range(num_tasks):
            thread_op.submit_task(cpu_intensive_task, task_size, f"thread_task_{i}")

        thread_results = thread_op.join_task("Processing ThreadPool tasks")
        print(thread_results)
        thread_time = time.time() - start_time

        logger.info(f"ThreadPool completed in {thread_time:.2f}s")

        # Test with Ray again for comparison
        ray_op2 = TestRayOp(name="ray_test_op2")

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
        error_op = TestRayOp(name="error_test_op")

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

        config_test_op = TestRayOp(name="config_test_op")
        config_test_op.submit_ray_task(cpu_intensive_task, 100, "config_test")

        logger.error("This should not be reached - Ray should be disabled")

    except RuntimeError as e:
        logger.info(f"✓ Correctly caught configuration error: {e}")

    finally:
        # Restore original configuration
        C.service_config.ray_max_workers = original_workers

    logger.info("\n=== Ray testing completed ===")


if __name__ == "__main__":
    run()
