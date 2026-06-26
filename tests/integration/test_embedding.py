"""Integration tests for embedding store through Application wiring."""

import asyncio
import sys
from pathlib import Path

import numpy as np

INTEGRATION_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(INTEGRATION_DIR))

# pylint: disable=wrong-import-position
from _workspace_fixture import workspace_env  # noqa: E402

from flowllm.enumeration import ComponentEnum  # noqa: E402
from flowllm.schema import EmbNode  # noqa: E402


def test_embedding_health_check():
    """health_check() returns True with a valid API key."""

    async def run():
        with workspace_env() as env:
            app = await env.make_app()
            try:
                store = app.context.components[ComponentEnum.EMBEDDING_STORE]["default"]
                result = await store.health_check(timeout=10.0)
                assert result is True, f"health_check returned {result}"
                assert store.is_healthy is True
                print("✓ test_embedding_health_check passed")
            finally:
                await env.close_all()

    asyncio.run(run())


def test_embedding_single_text():
    """Single text returns a valid embedding vector."""

    async def run():
        with workspace_env() as env:
            app = await env.make_app()
            try:
                store = app.context.components[ComponentEnum.EMBEDDING_STORE]["default"]
                emb = await store.get_embedding("Hello, world!")
                assert emb is not None, "get_embedding returned None"
                assert emb.shape == (store.dimensions,), f"shape {emb.shape} != ({store.dimensions},)"
                assert emb.dtype == np.float16, f"dtype {emb.dtype} != float16"
                assert np.linalg.norm(emb) > 0, "embedding is a zero vector"
                print(f"\n  [single] len={len(emb)}, first5={emb[:5].tolist()}")
                print("✓ test_embedding_single_text passed")
            finally:
                await env.close_all()

    asyncio.run(run())


def test_embedding_multiple_texts():
    """Batch embedding returns correct count and shape."""

    async def run():
        with workspace_env() as env:
            app = await env.make_app()
            try:
                store = app.context.components[ComponentEnum.EMBEDDING_STORE]["default"]
                texts = ["cat", "dog", "house"]
                results = await store.get_embeddings(texts)
                assert len(results) == 3, f"expected 3 results, got {len(results)}"
                for i, emb in enumerate(results):
                    assert emb is not None, f"result[{i}] is None"
                    assert emb.shape == (store.dimensions,), f"result[{i}] shape mismatch"
                    assert np.linalg.norm(emb) > 0, f"result[{i}] is a zero vector"
                    print(f"\n  [{texts[i]}] len={len(emb)}, first5={emb[:5].tolist()}")
                print("✓ test_embedding_multiple_texts passed")
            finally:
                await env.close_all()

    asyncio.run(run())


def test_embedding_cache_hit():
    """Repeated text returns cached result."""

    async def run():
        with workspace_env() as env:
            app = await env.make_app()
            try:
                store = app.context.components[ComponentEnum.EMBEDDING_STORE]["default"]
                text = "test caching behavior"
                emb1 = await store.get_embedding(text)
                cache_size_after_first = len(store._cache)  # pylint: disable=protected-access

                emb2 = await store.get_embedding(text)
                cache_size_after_second = len(store._cache)  # pylint: disable=protected-access

                assert emb1 is not None and emb2 is not None
                assert cache_size_after_second == cache_size_after_first, "cache grew on second call"
                assert np.array_equal(emb1, emb2), "cached embedding differs from original"
                print(f"\n  [cache] len={len(emb1)}, first5={emb1[:5].tolist()}")
                print("✓ test_embedding_cache_hit passed")
            finally:
                await env.close_all()

    asyncio.run(run())


def test_embedding_node_embeddings():
    """get_node_embeddings populates embedding on EmbNode objects."""

    async def run():
        with workspace_env() as env:
            app = await env.make_app()
            try:
                store = app.context.components[ComponentEnum.EMBEDDING_STORE]["default"]
                nodes = [
                    EmbNode(text="first node text"),
                    EmbNode(text="second node text"),
                ]
                result = await store.get_node_embeddings(nodes)
                assert result is nodes, "get_node_embeddings should return the same list"
                for i, node in enumerate(nodes):
                    assert node.embedding is not None, f"node[{i}].embedding is None"
                    assert node.embedding.shape == (store.dimensions,), f"node[{i}] shape mismatch"
                    print(f"\n  [node{i}] len={len(node.embedding)}, first5={node.embedding[:5].tolist()}")
                print("✓ test_embedding_node_embeddings passed")
            finally:
                await env.close_all()

    asyncio.run(run())


if __name__ == "__main__":
    print("=== Embedding integration tests ===")
    test_embedding_health_check()
    test_embedding_single_text()
    test_embedding_multiple_texts()
    test_embedding_cache_hit()
    test_embedding_node_embeddings()
    print("\nAll embedding integration tests passed!")
