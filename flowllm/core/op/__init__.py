"""Operation classes for flowllm framework.

This package provides the base classes and utilities for creating and composing
operations in the flowllm framework. Operations can be executed synchronously
or asynchronously, and can be composed sequentially or in parallel.
"""

from .base_async_op import BaseAsyncOp
from .base_async_tool_op import BaseAsyncToolOp
from .base_mcp_op import BaseMcpOp
from .base_op import BaseOp
from .base_ray_op import BaseRayOp
from .parallel_op import ParallelOp
from .sequential_op import SequentialOp

__all__ = [
    "BaseOp",
    "BaseAsyncOp",
    "BaseAsyncToolOp",
    "BaseMcpOp",
    "BaseRayOp",
    "SequentialOp",
    "ParallelOp",
]
