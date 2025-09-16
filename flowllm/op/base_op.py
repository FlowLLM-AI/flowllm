import copy
from abc import ABC
from pathlib import Path
from typing import List

from loguru import logger
from tqdm import tqdm

from flowllm.context.flow_context import FlowContext
from flowllm.context.prompt_handler import PromptHandler
from flowllm.context.service_context import C
from flowllm.embedding_model.base_embedding_model import BaseEmbeddingModel
from flowllm.llm.base_llm import BaseLLM
from flowllm.schema.service_config import LLMConfig, EmbeddingModelConfig
from flowllm.storage.vector_store.base_vector_store import BaseVectorStore
from flowllm.utils.common_utils import camel_to_snake
from flowllm.utils.timer import Timer


class BaseOp(ABC):
    file_path: str = __file__

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance._init_args = copy.copy(args)
        instance._init_kwargs = copy.copy(kwargs)
        return instance

    def __init__(self,
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
                 ops: list = None,
                 **kwargs):
        super().__init__()

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

        self.op_params: dict = kwargs

        self.task_list: list = []
        self.timer = Timer(name=self.name)
        self.context: FlowContext | None = None
        self.ops: List["BaseOp"] = ops

    def before_execute(self):
        ...

    def after_execute(self):
        ...

    def execute(self):
        ...

    def default_execute(self):
        ...

    def call(self, context: FlowContext = None):
        self.context = context
        with self.timer:
            if self.max_retries == 1 and self.raise_exception:
                self.before_execute()
                self.execute()
                self.after_execute()

            else:
                for i in range(self.max_retries):
                    try:
                        self.before_execute()
                        self.execute()
                        self.after_execute()

                    except Exception as e:
                        logger.exception(f"op={self.name} execute failed, error={e.args}")

                        if i == self.max_retries - 1:
                            if self.raise_exception:
                                raise e
                            else:
                                self.default_execute()

        if self.context is not None and self.context.response is not None:
            return self.context.response
        return None

    def submit_task(self, fn, *args, **kwargs) -> "BaseOp":
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
        assert self.async_mode == op.async_mode, f"async_mode must be the same. {self.async_mode}!={op.async_mode}"

    def __lshift__(self, op: "BaseOp"):
        self.check_async(op)
        self.ops = [op]
        return self

    def __rshift__(self, op: "BaseOp"):
        self.check_async(op)
        from flowllm.op.sequential_op import SequentialOp

        sequential_op = SequentialOp(ops=[self], async_mode=self.async_mode)

        if isinstance(op, SequentialOp):
            sequential_op.ops.extend(op.ops)
        else:
            sequential_op.ops.append(op)
        return sequential_op

    def __or__(self, op: "BaseOp"):
        self.check_async(op)
        from flowllm.op.parallel_op import ParallelOp

        parallel_op = ParallelOp(ops=[self], async_mode=self.async_mode)

        if isinstance(op, ParallelOp):
            parallel_op.ops.extend(op.ops)
        else:
            parallel_op.ops.append(op)

        return parallel_op

    def copy(self) -> "BaseOp":
        return self.__class__(*self._init_args, **self._init_kwargs)

    @property
    def llm(self) -> BaseLLM:
        if isinstance(self._llm, str):
            llm_config: LLMConfig = C.service_config.llm[self._llm]
            llm_cls = C.get_llm_class(llm_config.backend)
            self._llm = llm_cls(model_name=llm_config.model_name, **llm_config.params)

        return self._llm

    @property
    def embedding_model(self) -> BaseEmbeddingModel:
        if isinstance(self._embedding_model, str):
            embedding_model_config: EmbeddingModelConfig = C.service_config.embedding_model[self._embedding_model]
            embedding_model_cls = C.get_embedding_model_class(embedding_model_config.backend)
            self._embedding_model = embedding_model_cls(model_name=embedding_model_config.model_name,
                                                        **embedding_model_config.params)

        return self._embedding_model

    @property
    def vector_store(self) -> BaseVectorStore:
        if isinstance(self._vector_store, str):
            self._vector_store = C.get_vector_store(self._vector_store)
        return self._vector_store

    def prompt_format(self, prompt_name: str, **kwargs) -> str:
        return self.prompt.prompt_format(prompt_name=prompt_name, **kwargs)

    def get_prompt(self, prompt_name: str) -> str:
        return self.prompt.get_prompt(prompt_name=prompt_name)
