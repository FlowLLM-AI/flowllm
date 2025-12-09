"""Core Flow base class and sync/async execution helpers.

Defines `BaseFlow`, which builds an operation tree (`BaseOp`) and provides
sync (`call`) and async (`async_call`) entry points with optional streaming
support and structured error handling.

Caching:
- Non-streaming requests can be cached by enabling `enable_cache`.
- Cache key is an SHA-256 hash of the JSON-serialized request params (`**kwargs`).
- If params are not serializable, a serialization exception is logged and the
  call proceeds without caching.
- Cached value is the `FlowResponse` serialized via `model_dump()`, stored with
  an expiration configured by `cache_expire_hours`.
- Streaming (`stream=True`) is not cached.
"""

import asyncio
import hashlib
import json
from abc import ABC
from functools import partial
from typing import Union, Optional

from loguru import logger

from ..context import FlowContext, C, BaseContext
from ..enumeration import ChunkEnum
from ..op import BaseOp, SequentialOp, ParallelOp, BaseAsyncOp
from ..schema import FlowResponse, FlowStreamChunk
from ..storage import CacheHandler
from ..utils import camel_to_snake


class BaseFlow(ABC):
    """Abstract base class for all flows.

    Subclasses should implement `build_flow` to return a composed `BaseOp`.
    Instances support both streaming and non-streaming responses and can run
    either in the current thread or in an async loop depending on the
    underlying op's async capability.

    Caching is available for non-streaming paths when `enable_cache=True`.
    """

    def __init__(
        self,
        name: str = "",
        stream: bool = False,
        raise_exception: bool = True,
        enable_cache: bool = False,
        cache_path: str = "cache/{flow_name}",
        cache_expire_hours: float = 0.1,
        **kwargs,
    ):
        """Initialize a flow instance.

        Args:
            name: Flow name; defaults to the snake-cased class name.
            stream: Whether to stream output chunks.
            raise_exception: If False, capture exceptions into the response.
            enable_cache: Whether to enable response caching (non-stream only).
            cache_path: Cache storage path template with {flow_name} placeholder.
            cache_expire_hours: Cache expiration time in hours.
            **kwargs: Extra parameters passed to the flow context.
        """
        self.name: str = name or camel_to_snake(self.__class__.__name__)
        self.stream: bool = stream
        self.raise_exception: bool = raise_exception
        self.flow_params: dict = kwargs

        self._flow_op: Optional[BaseOp] = None
        self.flow_printed: bool = False
        self.enable_cache: bool = enable_cache
        self.cache_path: str = cache_path
        self.cache_expire_hours: float = cache_expire_hours
        self._cache: CacheHandler | None = None

    @property
    def cache(self) -> CacheHandler | None:
        """Lazily initialize and return the cache handler.

        Returns:
            A `CacheHandler` instance when caching is enabled; otherwise `None`.
        """
        if self.enable_cache and self._cache is None:
            self._cache = CacheHandler(self.cache_path.format(flow_name=self.name))
        return self._cache

    @staticmethod
    def _compute_cache_key(params: dict) -> Optional[str]:
        """Compute a stable cache key from request params.

        The key is `sha256(json.dumps(params, sort_keys=True))`. If serialization
        fails (e.g., params contain non-serializable objects), the error is logged
        and `None` is returned which disables caching for this call.

        Args:
            params: Request keyword arguments to serialize.

        Returns:
            Hex digest string key or `None` on serialization failure.
        """
        try:
            payload = json.dumps(params, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(payload.encode("utf-8")).hexdigest()

        except Exception as e:
            logger.exception(f"base_flow cache key serialization failed, error={e}")
            return None

    def _maybe_load_cached(self, params: dict) -> Optional[FlowResponse]:
        """Return cached response if available for non-streaming requests.

        Args:
            params: Request keyword arguments to compute the cache key.

        Returns:
            A `FlowResponse` if found in cache; otherwise `None`.
        """
        if not self.enable_cache or self.stream:
            return None

        key = self._compute_cache_key(params)
        if not key:
            return None

        cached = self.cache.load(key) if self.cache else None
        if cached is not None:
            logger.info(f"load flow response from cache with params={params}")
            return FlowResponse(**cached)

        return None

    def _maybe_save_cache(self, params: dict, response: FlowResponse):
        """Save a response into cache for non-streaming requests.

        Args:
            params: Request keyword arguments to compute the cache key.
            response: The `FlowResponse` to persist. Stored as `model_dump()`.
        """
        if not self.enable_cache or self.stream:
            return

        key = self._compute_cache_key(params)
        if not key:
            return

        if self.cache:
            self.cache.save(key, response.model_dump(), expire_hours=self.cache_expire_hours)

    @property
    def async_mode(self) -> bool:
        """Return whether the built op supports async execution."""
        return self.flow_op.async_mode

    def build_flow(self) -> BaseOp:
        """Build and return the root `BaseOp` for this flow.

        Subclasses must override this to construct the operation tree.
        """

    @property
    def flow_op(self):
        """Lazily build and cache the root operation for this flow."""
        if self._flow_op is None:
            self._flow_op = self.build_flow()
        return self._flow_op

    def print_flow(self):
        """Pretty-print the operation tree for debugging/logging once."""
        if not self.flow_printed:
            logger.info(f"---------- start print flow={self.name} ----------")
            self._print_operation_tree(self.flow_op, indent=0)
            logger.info(f"---------- end print flow={self.name} ----------")
            self.flow_printed = True

    def _print_operation_tree(self, op: BaseOp, indent: int):
        """Recursively log the structure of an operation tree.

        Args:
            op: Operation node to print.
            indent: Current indentation level for formatting.
        """
        prefix = "  " * indent
        if isinstance(op, SequentialOp):
            logger.info(f"{prefix}Sequential Execution:")
            for i, sub_op in enumerate(op.ops):
                logger.info(f"{prefix} Step {i + 1}:")
                self._print_operation_tree(sub_op, indent + 2)

        elif isinstance(op, ParallelOp):
            logger.info(f"{prefix}Parallel Execution:")
            for i, sub_op in enumerate(op.ops):
                logger.info(f"{prefix} Branch {i + 1}:")
                self._print_operation_tree(sub_op, indent + 2)

        else:
            logger.info(f"{prefix}Operation: {op.name}")
            if op.ops:
                if isinstance(op.ops, list):
                    for i, sub_op in enumerate(op.ops):
                        logger.info(f"{prefix} Sub {i + 1}:")
                        self._print_operation_tree(sub_op, indent + 2)
                elif isinstance(op.ops, BaseContext):
                    for key, sub_op in op.ops.items():
                        logger.info(f"{prefix} Sub {key}:")
                        self._print_operation_tree(sub_op, indent + 2)

    async def _async_call(self, context: FlowContext) -> Union[FlowResponse | FlowStreamChunk | None]:
        """Internal async executor that handles streaming and errors.

        Args:
            context: Flow execution context.

        Returns:
            `FlowResponse`, `FlowStreamChunk` (queue), or None when appropriate.
        """
        self.print_flow()

        # each time rebuild flow
        flow_op: BaseOp = self.build_flow()

        if self.async_mode:
            assert isinstance(flow_op, BaseAsyncOp)
            await flow_op.async_call(context=context)

        else:
            loop = asyncio.get_event_loop()
            op_call_fn = partial(flow_op.call, context=context)
            await loop.run_in_executor(executor=C.thread_pool, func=op_call_fn)

        if self.stream:
            await context.add_stream_done()
            return context.stream_queue
        else:
            return context.response

    async def async_call(self, **kwargs) -> Union[FlowResponse | FlowStreamChunk | None]:
        """Public async entry point for executing the flow.

        Keyword Args are forwarded to `FlowContext`.
        """
        kwargs["stream"] = self.stream

        # Cache only for non-streaming
        if not self.stream:
            cached = self._maybe_load_cached(kwargs)
            if cached is not None:
                return cached

        context = FlowContext(**kwargs)
        logger.info(f"request.params={kwargs}")

        if self.raise_exception:
            result = await self._async_call(context=context)
            if not self.stream:
                self._maybe_save_cache(kwargs, result)
            return result

        try:
            result = await self._async_call(context=context)
            if not self.stream:
                self._maybe_save_cache(kwargs, result)
            return result

        except Exception as e:
            logger.exception(f"flow_name={self.name} async call encounter error={e.args}")

            if self.stream:
                await context.add_stream_chunk_and_type(str(e), ChunkEnum.ERROR)
                await context.add_stream_done()
                return context.stream_queue

            else:
                context.add_response_error(e)
                return context.response

    def _call(self, context: FlowContext) -> FlowResponse:
        """Internal sync executor for flows without streaming."""
        self.print_flow()

        # each time rebuild flow
        flow_op: BaseOp = self.build_flow()

        if self.async_mode:
            assert isinstance(flow_op, BaseAsyncOp)
            asyncio.run(flow_op.async_call(context=context))

        else:
            flow_op.call(context=context)

        return context.response

    def call(self, **kwargs) -> FlowResponse:
        """Public sync entry point for executing the flow.

        Keyword Args are forwarded to `FlowContext`.
        """
        kwargs["stream"] = self.stream

        # Cache only for non-streaming
        if not self.stream:
            cached = self._maybe_load_cached(kwargs)
            if cached is not None:
                return cached

        context = FlowContext(**kwargs)
        logger.info(f"request.params={kwargs}")

        if self.raise_exception:
            result = self._call(context=context)
            if not self.stream:
                self._maybe_save_cache(kwargs, result)
            return result

        try:
            result = self._call(context=context)
            if not self.stream:
                self._maybe_save_cache(kwargs, result)
            return result

        except Exception as e:
            logger.exception(f"flow_name={self.name} call encounter error={e.args}")

            context.add_response_error(e)
            return context.response
