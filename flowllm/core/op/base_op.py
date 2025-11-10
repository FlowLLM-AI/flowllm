"""Base operation class for flowllm operations.

This module provides the BaseOp class, which serves as the foundation for all
operations in the flowllm framework. It includes support for synchronous and
asynchronous execution, caching, retries, and operation composition.
"""

import copy
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, List, Union

from loguru import logger
from tqdm import tqdm

from ..context import FlowContext, PromptHandler, C, BaseContext
from ..embedding_model import BaseEmbeddingModel
from ..llm import BaseLLM
from ..schema import LLMConfig, EmbeddingModelConfig
from ..storage import CacheHandler
from ..utils import Timer, camel_to_snake
from ..vector_store import BaseVectorStore


class BaseOp(ABC):
    """Base class for all operations in the flowllm framework.

    This class provides the core functionality for operations, including:
    - Synchronous and asynchronous execution modes
    - Retry mechanism with configurable retry counts
    - Caching support with expiration
    - Operation composition (sequential, parallel)
    - LLM, embedding model, and vector store integration
    - Prompt handling and formatting

    Prompt file convention:
        Each Op can be paired with a prompt configuration file for templates.
        By default, `prompt_path` is inferred from the Op's source file path by
        replacing the suffix "op.py" with "prompt.yaml". For example:

        - file: my_feature_op.py  -> prompt: my_feature_prompt.yaml
        - file: chat_op.py        -> prompt: chat_prompt.yaml

        This means the prompt file should be located in the same directory as
        the Op file, and named by replacing "op.py" with "prompt.yaml".

        You can override this behavior by explicitly passing `prompt_path` when
        initializing the Op.

    Attributes:
        name: Operation name, auto-generated from class name if not provided
        async_mode: Whether to run in async mode
        max_retries: Maximum number of retry attempts
        raise_exception: Whether to raise exceptions on failure
        enable_multithread: Whether to enable multithreading for task submission
        language: Language for prompt handling
        prompt_path: Path to prompt configuration file
        llm: LLM instance or configuration name
        embedding_model: Embedding model instance or configuration name
        vector_store: Vector store instance or configuration name
        enable_cache: Whether to enable caching
        cache_path: Cache storage path template
        cache_expire_hours: Cache expiration time in hours
        ops: List or dict of sub-operations
        op_params: Additional operation parameters
        context: Current execution context
        timer: Timer for tracking execution time

    Example:
        ```python
        class MyOp(BaseOp):
            def execute(self):
                return "result"

        op = MyOp()
        result = op.call()
        ```
    """

    file_path: str = __file__

    def __new__(cls, *args, **kwargs):
        """Create a new instance and save initialization arguments for copying.

        Args:
            *args: Positional arguments passed to __init__
            **kwargs: Keyword arguments passed to __init__

        Returns:
            New instance with saved initialization arguments
        """
        instance = super().__new__(cls)
        instance._init_args = copy.copy(args)
        instance._init_kwargs = copy.copy(kwargs)
        return instance

    def __init__(
        self,
        name: str = "",
        async_mode: bool = False,
        max_retries: int = 1,
        raise_exception: bool = True,
        enable_multithread: bool = True,
        language: str = "",
        prompt_path: str = "",
        llm: str = "default",
        embedding_model: str = "default",
        vector_store: str = "default",
        enable_cache: bool = False,
        cache_path: str = "cache/{op_name}",
        cache_expire_hours: float = 0.1,
        ops: List["BaseOp"] = None,
        **kwargs,
    ):
        """Initialize the base operation.

        Args:
            name: Operation name, auto-generated if empty
            async_mode: Whether to run in async mode
            max_retries: Maximum number of retry attempts
            raise_exception: Whether to raise exceptions on failure
            enable_multithread: Whether to enable multithreading
            language: Language for prompt handling
            prompt_path: Path to prompt configuration file. If not provided, it
                will be inferred by replacing the Op file's suffix "op.py" with
                "prompt.yaml" (same directory). For example:
                - `xxx_op.py` -> `xxx_prompt.yaml`
            llm: LLM configuration name or instance
            embedding_model: Embedding model configuration name or instance
            vector_store: Vector store configuration name or instance
            enable_cache: Whether to enable caching
            cache_path: Cache storage path template with {op_name} placeholder
            cache_expire_hours: Cache expiration time in hours
            ops: List of sub-operations
            **kwargs: Additional operation parameters
        """
        super().__init__()
        assert self.__class__.__name__.endswith("Op"), f"class_name={self.__class__.__name__} must end with 'Op'"

        self.name: str = name or camel_to_snake(self.__class__.__name__)
        self.async_mode: bool = async_mode
        self.max_retries: int = max_retries
        self.raise_exception: bool = raise_exception
        self.enable_multithread: bool = enable_multithread
        self.language: str = language or C.language
        default_prompt_path: str = self.file_path.replace("op.py", "prompt.yaml")
        self.prompt_path: Path = Path(prompt_path if prompt_path else default_prompt_path)
        self.prompt = PromptHandler(language=self.language).load_prompt_by_file(self.prompt_path)
        self._llm: BaseLLM | str = llm
        self._embedding_model: BaseEmbeddingModel | str = embedding_model
        self._vector_store: BaseVectorStore | str = vector_store
        self.enable_cache: bool = enable_cache
        self.cache_path: str = cache_path
        self.cache_expire_hours: float = cache_expire_hours
        self.ops: List["BaseOp"] | BaseContext = ops if ops else BaseContext()
        self.op_params: dict = kwargs

        self.task_list: list = []
        self.timer = Timer(name=self.name)
        self.context: FlowContext | None = None
        self._cache: CacheHandler | None = None

    @property
    def short_name(self) -> str:
        """Get the short name of the operation (without '_op' suffix).

        Returns:
            Short name without '_op' suffix
        """
        return self.name.rstrip("_op")

    @property
    def cache(self):
        """Get the cache handler instance (lazy initialization).

        Returns:
            CacheHandler instance if caching is enabled, None otherwise
        """
        if self.enable_cache and self._cache is None:
            self._cache = CacheHandler(self.cache_path.format(op_name=self.short_name))
        return self._cache

    def save_load_cache(self, key: str, fn: Callable, **kwargs):
        """Save or load from cache.

        If caching is enabled, checks cache first. If not found, executes the
        function and saves the result. Otherwise, executes the function directly.

        Args:
            key: Cache key for storing/retrieving the result
            fn: Function to execute if cache miss
            **kwargs: Additional arguments for cache load operation

        Returns:
            Cached result if available, otherwise result from function execution
        """
        if self.enable_cache:
            result = self.cache.load(key, **kwargs)
            if result is None:
                result = fn()
                self.cache.save(key, result, expire_hours=self.cache_expire_hours)
            else:
                logger.info(f"load {key} from cache")
        else:
            result = fn()

        return result

    def before_execute(self):
        """Hook method called before execute(). Override in subclasses."""

    def after_execute(self):
        """Hook method called after execute(). Override in subclasses."""

    @abstractmethod
    def execute(self):
        """Main execution method. Must be implemented in subclasses.

        Returns:
            Execution result
        """

    def default_execute(self):
        """Default execution method when main execution fails. Override in subclasses.

        Returns:
            Default execution result
        """

    @staticmethod
    def build_context(context: FlowContext = None, **kwargs):
        """Build or update a flow context.

        Args:
            context: Existing flow context, creates new one if None
            **kwargs: Additional context updates

        Returns:
            FlowContext instance with updates applied
        """
        if not context:
            context = FlowContext()
        if kwargs:
            context.update(kwargs)
        return context

    def call(self, context: FlowContext = None, **kwargs):
        """Execute the operation synchronously.

        This method handles the full execution lifecycle including retries,
        error handling, and context management.

        Args:
            context: Flow context for this execution
            **kwargs: Additional context updates

        Returns:
            Execution result, context response, or None
        """
        self.context = self.build_context(context, **kwargs)
        with self.timer:
            result = None
            if self.max_retries == 1 and self.raise_exception:
                self.before_execute()
                result = self.execute()
                self.after_execute()

            else:
                for i in range(self.max_retries):
                    try:
                        self.before_execute()
                        result = self.execute()
                        self.after_execute()
                        break

                    except Exception as e:
                        logger.exception(f"op={self.name} execute failed, error={e.args}")

                        if i == self.max_retries - 1:
                            if self.raise_exception:
                                raise e

                            result = self.default_execute()  # pylint: disable=E1111

        if result is not None:
            return result

        elif self.context is not None and self.context.response is not None:
            return self.context.response

        else:
            return None

    def submit_task(self, fn, *args, **kwargs) -> "BaseOp":
        """Submit a task for execution (multithreaded or synchronous).

        Args:
            fn: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Self for method chaining
        """
        if self.enable_multithread:
            task = C.thread_pool.submit(fn, *args, **kwargs)
            self.task_list.append(task)

        else:
            result = fn(*args, **kwargs)
            if result:
                if isinstance(result, list):
                    result.extend(result)
                else:
                    result.append(result)

        return self

    def join_task(self, task_desc: str = None) -> list:
        """Wait for all submitted tasks to complete and collect results.

        Args:
            task_desc: Description for progress bar display

        Returns:
            List of task results
        """
        result = []
        if self.enable_multithread:
            for task in tqdm(self.task_list, desc=task_desc or self.name):
                t_result = task.result()
                if t_result:
                    if isinstance(t_result, list):
                        result.extend(t_result)
                    else:
                        result.append(t_result)

        else:
            result.extend(self.task_list)

        self.task_list.clear()
        return result

    def check_async(self, op: "BaseOp"):
        """Check if the given operation has the same async mode as self.

        Args:
            op: Operation to check

        Raises:
            AssertionError: If async modes don't match
        """
        assert self.async_mode == op.async_mode, f"async_mode must be the same. {self.async_mode}!={op.async_mode}"

    def add_op(self, op: "BaseOp", name: str = ""):
        """Add a sub-operation to this operation.

        Args:
            op: Operation to add
            name: Name for the operation (only used if ops is a dict)
        """
        if isinstance(self.ops, list):
            self.ops.append(op)
        else:
            if not name:
                name = op.name
            self.ops[name] = op

    def __lshift__(self, ops: Union["BaseOp", dict, list]):
        """Left shift operator for adding operations (op << other_op, op << {"search": op1, "find": op2}).

        Args:
            ops: Operation(s) to add - can be BaseOp, dict of ops, or list of ops

        Returns:
            Self for method chaining

        Raises:
            ValueError: If op type is invalid
        """
        if isinstance(ops, BaseOp):
            self.check_async(ops)
            self.add_op(ops)

        elif isinstance(ops, dict):
            for name, op in ops.items():
                self.add_op(op, name)

        elif isinstance(ops, list):
            for op in ops:
                self.add_op(op)

        else:
            raise ValueError(f"Invalid op type: {type(ops)}")

        return self

    def __rshift__(self, op: "BaseOp"):
        """Right shift operator for creating sequential operations (op >> other_op).

        Args:
            op: Operation to chain sequentially

        Returns:
            SequentialOp containing self and op
        """
        self.check_async(op)
        from .sequential_op import SequentialOp

        sequential_op = SequentialOp(ops=[self], async_mode=self.async_mode)

        if isinstance(op, SequentialOp):
            sequential_op.ops.extend(op.ops)
        else:
            sequential_op.ops.append(op)
        return sequential_op

    def __or__(self, op: "BaseOp"):
        """Bitwise OR operator for creating parallel operations (op | other_op).

        Args:
            op: Operation to run in parallel

        Returns:
            ParallelOp containing self and op
        """
        self.check_async(op)
        from .parallel_op import ParallelOp

        parallel_op = ParallelOp(ops=[self], async_mode=self.async_mode)

        if isinstance(op, ParallelOp):
            parallel_op.ops.extend(op.ops)
        else:
            parallel_op.ops.append(op)

        return parallel_op

    def copy(self, **kwargs):
        """Create a deep copy of this operation.

        Args:
            **kwargs: Additional parameters to override in the copy

        Returns:
            New operation instance with copied configuration
        """
        copy_op = self.__class__(*self._init_args, **self._init_kwargs, **kwargs)
        if self.ops:
            if isinstance(self.ops, list):
                copy_op.ops.clear()
                for op in self.ops:
                    copy_op.ops.append(op.copy())

            elif isinstance(self.ops, BaseContext):
                copy_op.ops.clear()
                for name, op in self.ops.items():
                    copy_op.ops[name] = op.copy()

            else:
                raise NotImplementedError("ops type not supported")

        return copy_op

    @property
    def llm(self) -> BaseLLM:
        """Get the LLM instance (lazy initialization).

        Returns:
            BaseLLM instance configured from service config
        """
        if isinstance(self._llm, str):
            llm_config: LLMConfig = C.service_config.llm[self._llm]
            llm_cls = C.get_llm_class(llm_config.backend)
            self._llm = llm_cls(model_name=llm_config.model_name, **llm_config.params)

        return self._llm

    @property
    def embedding_model(self) -> BaseEmbeddingModel:
        """Get the embedding model instance (lazy initialization).

        Returns:
            BaseEmbeddingModel instance configured from service config
        """
        if isinstance(self._embedding_model, str):
            embedding_model_config: EmbeddingModelConfig = C.service_config.embedding_model[self._embedding_model]
            embedding_model_cls = C.get_embedding_model_class(embedding_model_config.backend)
            self._embedding_model = embedding_model_cls(
                model_name=embedding_model_config.model_name,
                **embedding_model_config.params,
            )

        return self._embedding_model

    @property
    def vector_store(self) -> BaseVectorStore:
        """Get the vector store instance (lazy initialization).

        Returns:
            BaseVectorStore instance configured from service config
        """
        if isinstance(self._vector_store, str):
            self._vector_store = C.get_vector_store(self._vector_store)
        return self._vector_store

    def prompt_format(self, prompt_name: str, **kwargs) -> str:
        """Format a prompt template with provided variables.

        Args:
            prompt_name: Name of the prompt template
            **kwargs: Variables to substitute in the template

        Returns:
            Formatted prompt string
        """
        return self.prompt.prompt_format(prompt_name=prompt_name, **kwargs)

    def get_prompt(self, prompt_name: str) -> str:
        """Get a prompt template by name.

        Args:
            prompt_name: Name of the prompt template

        Returns:
            Prompt template string
        """
        return self.prompt.get_prompt(prompt_name=prompt_name)
