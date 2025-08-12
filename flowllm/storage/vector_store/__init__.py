from old.utils.registry import Registry

VECTOR_STORE_REGISTRY = Registry()

from old.vector_store.es_vector_store import EsVectorStore
from old.vector_store.chroma_vector_store import ChromaVectorStore
from old.vector_store.file_vector_store import FileVectorStore
