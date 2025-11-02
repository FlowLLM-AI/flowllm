"""Operation classes for flowllm framework.

This package provides the base classes and utilities for creating and composing
operations in the flowllm framework. Operations can be executed synchronously
or asynchronously, and can be composed sequentially or in parallel.
"""

from .base_async_op import BaseAsyncOp
from .base_op import BaseOp
from .parallel_op import ParallelOp
from .sequential_op import SequentialOp

__all__ = [
    "BaseOp",
    "BaseAsyncOp",
    "SequentialOp",
    "ParallelOp",
]
