from abc import ABC
from pathlib import Path

from flowllm.context.prompt_context import PromptContext
from flowllm.context.registry_context import get_llm, get_embedding_model
from flowllm.embedding_model.base_embedding_model import BaseEmbeddingModel
from flowllm.llm.base_llm import BaseLLM
from flowllm.op.base_op import BaseOp
from flowllm.schema.service_config import LLMConfig, EmbeddingModelConfig
from flowllm.storage.vector_store.base_vector_store import BaseVectorStore


class BaseLLMOp(BaseOp, ABC):
    current_path: str = __file__

    def __init__(self,
                 llm: str = "default",
                 embedding_model: str = "default",
                 vector_store: str = "default",
                 **kwargs):

        super().__init__(**kwargs)

        self._llm: BaseLLM | str = llm
        self._embedding_model: BaseEmbeddingModel | str = embedding_model
        self._vector_store: BaseVectorStore | str = vector_store

        self.prompt = PromptContext()
        self._prepare_prompt()

    def _prepare_prompt(self):
        prompt_file_name = self.name.replace("_op", "_prompt.yaml")
        prompt_file_path = Path(self.current_path).parent / prompt_file_name
        self.prompt.load_prompt_by_file(prompt_file_path)

    @property
    def llm(self) -> BaseLLM:
        if isinstance(self._llm, str):
            llm_config: LLMConfig = self.flow_context.service_config.llm[self._llm]
            llm_cls = get_llm(llm_config.backend)
            self._llm = llm_cls(model_name=llm_config.model_name, **llm_config.params)

        return self._llm

    @property
    def embedding_model(self) -> BaseEmbeddingModel:
        if isinstance(self._embedding_model, str):
            embedding_model_config: EmbeddingModelConfig = \
                self.flow_context.service_config.embedding_model[self._embedding_model]
            embedding_model_cls = get_embedding_model(embedding_model_config.backend)
            self._embedding_model = embedding_model_cls(model_name=embedding_model_config.model_name,
                                                        **embedding_model_config.params)

        return self._embedding_model

    @property
    def vector_store(self) -> BaseVectorStore:
        if isinstance(self._vector_store, str):
            self._vector_store = self.service_context.get_vector_store(self._vector_store)
        return self._vector_store

    def prompt_format(self, prompt_name: str, **kwargs) -> str:
        return self.prompt.prompt_format(prompt_name=prompt_name, **kwargs)

    def get_prompt(self, prompt_name: str) -> str:
        return self.prompt.get_prompt(prompt_name=prompt_name)
