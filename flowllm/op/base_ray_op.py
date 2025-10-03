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

    def submit_and_join_parallel_op(self,
                                    op: BaseOp,
                                    parallel_key: str = "",
                                    enable_test: bool = False,
                                    **kwargs):

        def fn_wrapper():
            op.call()
            return result

        return self.submit_and_join_ray_task(op.call,
                                             parallel_key=parallel_key,
                                             task_desc=f"collect {op.short_name} parallel result",
                                             enable_test=enable_test,
                                             **kwargs)

    def submit_and_join_ray_task(self,
                                 fn,
                                 parallel_key: str = "",
                                 task_desc: str = "",
                                 enable_test: bool = False,
                                 **kwargs):
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
