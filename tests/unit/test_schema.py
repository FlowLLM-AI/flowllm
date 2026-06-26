"""Unit tests for pydantic schema helpers."""

import numpy as np

from flowllm.enumeration import ComponentEnum
from flowllm.schema import ApplicationConfig, ComponentConfig, EmbNode, Request, Response


def test_emb_node_coerces_embedding_to_float16_and_serializes_to_list():
    """Embedding vectors accept plain lists and remain JSON serializable."""
    node = EmbNode(text="hello", embedding=[1.25, 2.5], metadata={"source": "unit"})

    assert isinstance(node.embedding, np.ndarray)
    assert node.embedding.dtype == np.float16
    assert node.model_dump()["embedding"] == [1.25, 2.5]
    assert node.metadata == {"source": "unit"}


def test_request_response_component_config_allow_extra_fields():
    """Schemas intentionally preserve backend-specific payload fields."""
    request = Request(metadata={"trace_id": "1"}, query="hello")
    response = Response(answer="ok", score=0.9)
    component = ComponentConfig(backend="custom", host="127.0.0.1")

    assert request.query == "hello"
    assert response.score == 0.9
    assert component.host == "127.0.0.1"


def test_application_config_accepts_component_enum_keys():
    """Component config maps can be keyed by ComponentEnum values."""
    config = ApplicationConfig(
        components={
            ComponentEnum.CLIENT: {
                "http": ComponentConfig(backend="http"),
            },
        },
    )

    assert config.components[ComponentEnum.CLIENT]["http"].backend == "http"
