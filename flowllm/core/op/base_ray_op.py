"""Base Ray operation class for distributed parallel execution.

This module provides the BaseRayOp class, which extends BaseOp with Ray-based
distributed parallelization capabilities. It allows operations to be executed
in parallel across multiple workers using Ray for efficient distributed computing.
"""

from abc import ABC

import pandas as pd
from loguru import logger
from tqdm import tqdm

from .base_op import BaseOp
from ..context import BaseContext, C


class BaseRayOp(BaseOp, ABC):
    """Base class for operations with Ray-based distributed parallelization.

    This class extends BaseOp to provide distributed parallel execution using Ray.
    It automatically detects list parameters for parallelization and distributes
    work across multiple Ray workers. Large data structures (DataFrames, Series,
    dicts, lists, Contexts) are automatically converted to Ray objects for
    efficient sharing across workers.

    Attributes:
        ray_task_list: List of Ray task futures being tracked

    Example:
        ```python
        class MyRayOp(BaseRayOp):
            def execute(self):
                # Automatically parallelizes over 'items' list
                results = self.submit_and_join_ray_task(
                    fn=process_item,
                    items=[1, 2, 3, 4, 5],
                    other_param="value"
                )
                return results
        ```
    """

    def __init__(self, **kwargs):
        """Initialize the Ray operation.

        Args:
            **kwargs: Arguments passed to BaseOp.__init__
        """
        super().__init__(**kwargs)
        self.ray_task_list = []

    def submit_and_join_parallel_op(self, op: BaseOp, **kwargs):
        """Submit a parallel operation and wait for all results.

        Automatically detects the first list parameter in kwargs as the parallel key
        and distributes the operation's execution across Ray workers.

        Args:
            op: BaseOp instance to execute in parallel
            **kwargs: Arguments to pass to op.call(), must contain at least one list

        Returns:
            List of results from all parallel executions

        Raises:
            AssertionError: If no list parameter is found in kwargs
        """
        parallel_key = None
        for key, value in kwargs.items():
            if isinstance(value, list):
                parallel_key = key
                logger.info(f"using first list parallel_key={parallel_key}")
                break
        assert parallel_key is not None

        return self.submit_and_join_ray_task(
            fn=op.call,
            parallel_key=parallel_key,
            task_desc=f"{op.short_name}.parallel",
            context=self.context,
            **kwargs,
        )

    def submit_and_join_ray_task(
        self,
        fn,
        parallel_key: str = "",
        task_desc: str = "",
        **kwargs,
    ):
        """Submit Ray tasks for parallel execution and wait for all results.

        This method distributes work across multiple Ray workers by splitting a
        list parameter. Large data structures are automatically converted to Ray
        objects for efficient sharing.

        Args:
            fn: Function to execute in parallel. Will be called with each item
                from the parallel_list as the parallel_key parameter.
            parallel_key: Name of the keyword argument containing the list to
                parallelize over. If empty, auto-detects the first list parameter.
            task_desc: Description for progress bar display
            **kwargs: Additional arguments to pass to fn. Large data structures
                (DataFrame, Series, dict, list, BaseContext) are converted to
                Ray objects automatically.

        Returns:
            List of results from all parallel executions, flattened if individual
            results are lists

        Raises:
            AssertionError: If no list parameter is found when parallel_key is empty
            RuntimeError: If Ray is not configured (ray_max_workers <= 1)
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
            if isinstance(value, pd.DataFrame | pd.Series | dict | list | BaseContext):
                kwargs[key] = ray.put(value)

        # Create and submit tasks for each worker
        for i in range(max_workers):
            self.submit_ray_task(
                fn=self.ray_task_loop,
                parallel_key=parallel_key,
                parallel_list=parallel_list,
                actor_index=i,
                max_workers=max_workers,
                internal_fn=fn,
                **kwargs,
            )
            logger.info(f"ray.submit task_desc={task_desc} id={i}")

        # Wait for all tasks to complete and collect results
        result = self.join_ray_task(task_desc=task_desc)
        logger.info(f"{task_desc} complete. result_size={len(result)} resources={ray.available_resources()}")
        return result

    @staticmethod
    def ray_task_loop(
        parallel_key: str,
        parallel_list: list,
        actor_index: int,
        max_workers: int,
        internal_fn,
        **kwargs,
    ):
        """Worker loop that processes a subset of items from parallel_list.

        Each worker processes items assigned to it based on actor_index and
        max_workers using a round-robin distribution (items[actor_index::max_workers]).

        Args:
            parallel_key: Name of the keyword argument to set with parallel_value
            parallel_list: Full list of items to process
            actor_index: Index of this worker (0 to max_workers-1)
            max_workers: Total number of workers
            internal_fn: Function to call for each item
            **kwargs: Additional arguments to pass to internal_fn

        Returns:
            List of results from processing assigned items
        """
        result = []
        for parallel_value in parallel_list[actor_index::max_workers]:
            kwargs.update({"actor_index": actor_index, parallel_key: parallel_value})
            t_result = internal_fn(**kwargs)
            if t_result:
                if isinstance(t_result, list):
                    result.extend(t_result)
                else:
                    result.append(t_result)
        return result

    def submit_ray_task(self, fn, *args, **kwargs):
        """Submit a single Ray task for asynchronous execution.

        Initializes Ray if not already initialized and creates a remote function
        to execute the task. The task is added to ray_task_list for later joining.

        Args:
            fn: Function to execute remotely
            *args: Positional arguments for fn
            **kwargs: Keyword arguments for fn

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
        """Wait for all submitted Ray tasks to complete and collect results.

        Processes tasks with a progress bar and collects results. If individual
        results are lists, they are flattened into the final result list.

        Args:
            task_desc: Description for progress bar display. If None, uses
                "{self.name}_ray"

        Returns:
            List of all task results, flattened if individual results are lists
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
