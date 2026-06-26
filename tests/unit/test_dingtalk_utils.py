"""Unit tests for DingTalk utilities."""

import pytest

from flowllm.utils import dingtalk_utils


class FakeResponse:
    """Minimal response object for httpx.post tests."""

    text = '{"errcode":0}'

    def raise_for_status(self) -> None:
        """Match the httpx response API used by the helper."""
        return None


def test_send_dingtalk_markdown_message(monkeypatch):
    """Verify markdown messages use the channel token and payload shape."""
    seen = {}
    monkeypatch.setenv("DING_TEST_API_TOKEN", "test-token")
    monkeypatch.setattr(dingtalk_utils, "load_env", lambda: {})

    def fake_post(url, json, timeout):
        seen["url"] = url
        seen["json"] = json
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(dingtalk_utils.httpx, "post", fake_post)

    result = dingtalk_utils.send_dingtalk_message(
        "Build",
        "**done**",
        channel="test",
        timeout=3,
    )

    assert result == '{"errcode":0}'
    assert seen["url"] == "https://oapi.dingtalk.com/robot/send?access_token=test-token"
    assert seen["json"] == {
        "msgtype": "markdown",
        "markdown": {"title": "Build", "text": "**done**"},
    }
    assert seen["timeout"] == 3


def test_send_dingtalk_text_message(monkeypatch):
    """Verify text messages send content under the text key."""
    seen = {}
    monkeypatch.setenv("DING_DAILY_API_TOKEN", "daily-token")
    monkeypatch.setattr(dingtalk_utils, "load_env", lambda: {})

    def fake_post(_url, json, timeout):
        seen["json"] = json
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(dingtalk_utils.httpx, "post", fake_post)

    dingtalk_utils.send_dingtalk_message("Ignored", "hello", msgtype="text")

    assert seen["json"] == {"msgtype": "text", "text": {"content": "hello"}}
    assert seen["timeout"] == 10.0


def test_send_dingtalk_message_requires_token(monkeypatch):
    """Verify a missing token fails before sending a request."""
    monkeypatch.delenv("DING_DAILY_API_TOKEN", raising=False)
    monkeypatch.setattr(dingtalk_utils, "load_env", lambda: {})

    with pytest.raises(ValueError, match="DING_DAILY_API_TOKEN"):
        dingtalk_utils.send_dingtalk_message("title", "text")


def test_send_dingtalk_message_validates_options():
    """Verify invalid options are rejected."""
    with pytest.raises(ValueError, match="Unsupported channel"):
        dingtalk_utils.send_dingtalk_message("title", "text", channel="other")

    with pytest.raises(ValueError, match="Unsupported message type"):
        dingtalk_utils.send_dingtalk_message("title", "text", msgtype="json")
