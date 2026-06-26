"""Tests for service job registration."""

from types import SimpleNamespace

from flowllm.components.job import BaseJob, StreamJob
from flowllm.components.service import MCPService


def _dummy_app():
    """Minimal MCPService.build_service stub."""

    async def start():
        return None

    async def close():
        return None

    return SimpleNamespace(
        config=SimpleNamespace(app_name="test"),
        context=SimpleNamespace(metadata={}),
        start=start,
        close=close,
    )


def test_mcp_service_registers_job_with_empty_parameters():
    """Empty parameters remain a dict for FastMCP validation."""
    service = MCPService()
    service.build_service(_dummy_app())

    job = BaseJob(name="empty_params", parameters={})

    assert service.add_job(job) is True


def test_mcp_service_reports_stream_job_skipped():
    """StreamJob tools are not exposed by MCPService."""
    service = MCPService()
    service.build_service(_dummy_app())

    job = StreamJob(name="stream")

    assert service.add_job(job) is False
