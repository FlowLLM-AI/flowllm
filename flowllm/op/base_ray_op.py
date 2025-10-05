from abc import ABC

import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.context.base_context import BaseContext
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

    def submit_and_join_parallel_op(self, op: BaseOp, **kwargs):
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
