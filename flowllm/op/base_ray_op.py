from abc import ABC

import ray
from loguru import logger
from tqdm import tqdm

from flowllm.context.service_context import C
from flowllm.op.base_op import BaseOp


class BaseRayOp(BaseOp, ABC):

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
    run()
