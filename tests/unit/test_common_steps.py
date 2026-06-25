"""Tests for flowllm common steps with only local dependencies."""

# pylint: disable=protected-access

import asyncio
import warnings

from flowllm.components.agent_wrapper import BaseAgentWrapper
from flowllm.steps.common.add import AddStep
from flowllm.steps.common.health_check import _file_graph_status
from flowllm.steps.common.llm_demo import LLMDemoStep

warnings.filterwarnings("ignore", category=DeprecationWarning, module="jieba")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pkg_resources")


def _run(coro):
    """Run an async coroutine on a fresh isolated event loop."""
    asyncio.run(coro)


def test_add_step_coerces_numeric_inputs():
    """add accepts numeric strings as numbers, not string concatenation."""

    async def run():
        step = AddStep()
        resp = await step(a="1", b="2.5")
        assert resp.success is True
        assert resp.answer == "3.5"
        assert resp.metadata["result"] == 3.5
        print("✓ test_add_step_coerces_numeric_inputs passed")

    _run(run())


def test_add_step_rejects_invalid_inputs():
    """invalid add arguments should return a failed response instead of throwing or concatenating."""

    async def run():
        step = AddStep()
        resp = await step(a="one", b=2)
        assert resp.success is False
        assert "Invalid add arguments" in resp.answer
        print("✓ test_add_step_rejects_invalid_inputs passed")

    _run(run())


class _FakeAgentWrapper(BaseAgentWrapper):
    """Capture reply kwargs without calling a real model."""

    def __init__(self):
        super().__init__()
        self.last_kwargs = None

    async def reply(self, inputs, **kwargs) -> dict:
        self.last_kwargs = kwargs
        return {"result": "ok"}


def test_llm_demo_always_registers_add_tool():
    """LLM demo always passes the add job as a tool."""

    async def run():
        wrapper = _FakeAgentWrapper()
        step = LLMDemoStep()
        resp = await step(query="hello", agent_wrapper=wrapper)
        assert resp.success is True
        assert wrapper.last_kwargs["job_tools"] == ["add"]
        assert "job_tools" not in resp.metadata
        print("✓ test_llm_demo_always_registers_add_tool passed")

    _run(run())


def test_file_graph_health_reports_neo4j_cached_counts():
    """Neo4j file graph health should not be reported as an empty local graph."""

    class FakeNeo4jGraph:
        """Minimal Neo4j graph stub with cached health counters."""

        is_started = True
        _driver = object()
        _uri = "bolt://example"
        _database = "neo4j"
        _n_nodes = 3
        _n_edges = 4
        _n_virtual = 1

    status = _file_graph_status(FakeNeo4jGraph())
    assert status["n_nodes"] == 3
    assert status["n_edges"] == 4
    assert status["n_virtual"] == 1
    print("✓ test_file_graph_health_reports_neo4j_cached_counts passed")
