from abc import ABC

import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.context.base_context import BaseContext
from flowllm.context.service_context import C
from flowllm.op.base_op import BaseOp


class BaseRayOp(BaseOp, ABC):
    """
    Base class for Ray-based operations that provides distributed parallel execution.
    
    Extends BaseOp to support Ray distributed computing framework.
    Ray enables scaling operations across multiple CPU cores or even multiple machines.
    
    Key features:
    - Distributed task execution across Ray workers
    - Automatic data serialization with Ray's object store
    - Load balancing across available workers
    - Progress tracking with tqdm
    
    Use this when you need:
    - Heavy parallelism beyond thread pool limits
    - Processing large datasets in parallel
    - Distributed computing across multiple machines
    """

    def __init__(self, **kwargs):
        """Initialize Ray operation with empty task list."""
        super().__init__(**kwargs)
        self.ray_task_list = []

    def submit_and_join_parallel_op(self, op: BaseOp, **kwargs):
        """
        Helper to parallelize an operation over a list parameter.
        
        Automatically detects the first list parameter and parallelizes the operation
        across all values in that list.
        
        Args:
            op: Operation to parallelize
            **kwargs: Parameters including at least one list to parallelize over
            
        Returns:
            Combined results from all parallel executions
        """
        parallel_key = None
        for key, value in kwargs.items():
            if isinstance(value, list):
                parallel_key = key
                logger.info(f"using first list parallel_key={parallel_key}")
                break
        assert parallel_key is not None

        return self.submit_and_join_ray_task(fn=op.call,
                                             parallel_key=parallel_key,
                                             task_desc=f"{op.short_name}.parallel",
                                             context=self.context,
                                             **kwargs)

    def submit_and_join_ray_task(self,
                                 fn,
                                 parallel_key: str = "",
                                 task_desc: str = "",
                                 **kwargs):
        """
        Parallelize a function across Ray workers with automatic load balancing.
        
        This method:
        1. Auto-detects the list parameter to parallelize over (if not specified)
        2. Converts large objects (DataFrames, dicts, etc.) to Ray objects for efficiency
        3. Distributes work across workers using round-robin scheduling
        4. Collects and combines all results
        
        Args:
            fn: Function to execute in parallel (receives one item from parallel_key list)
            parallel_key: Name of the list parameter to parallelize over (auto-detected if empty)
            task_desc: Description for progress bar
            **kwargs: Parameters for fn, one should be a list to parallelize over
            
        Returns:
            Combined list of results from all workers
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
            self.submit_ray_task(fn=self.ray_task_loop,
                                 parallel_key=parallel_key,
                                 parallel_list=parallel_list,
                                 actor_index=i,
                                 max_workers=max_workers,
                                 internal_fn=fn,
                                 **kwargs)
            logger.info(f"ray.submit task_desc={task_desc} id={i}")

        # Wait for all tasks to complete and collect results
        result = self.join_ray_task(task_desc=task_desc)
        logger.info(f"{task_desc} complete. result_size={len(result)} resources={ray.available_resources()}")
        return result

    @staticmethod
    def ray_task_loop(parallel_key: str, parallel_list: list, actor_index: int, max_workers: int, internal_fn, **kwargs):
        """
        Worker loop that processes a subset of the parallel list.
        
        Each worker processes every Nth item (round-robin scheduling) where N = max_workers.
        For example, with 4 workers:
        - Worker 0: items 0, 4, 8, 12, ...
        - Worker 1: items 1, 5, 9, 13, ...
        - Worker 2: items 2, 6, 10, 14, ...
        - Worker 3: items 3, 7, 11, 15, ...
        
        Args:
            parallel_key: Name of the list parameter
            parallel_list: Full list to process
            actor_index: This worker's index (0 to max_workers-1)
            max_workers: Total number of workers
            internal_fn: Function to call for each item
            **kwargs: Additional parameters for internal_fn
            
        Returns:
            Combined results from all items processed by this worker
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
