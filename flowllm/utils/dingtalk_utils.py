"""DingTalk robot message helpers."""

import os
from typing import Literal

import httpx

from .env_utils import load_env

DingTalkChannel = Literal["test", "daily"]
DingTalkMessageType = Literal["markdown", "text"]


def send_dingtalk_message(
    title: str,
    text: str,
    channel: DingTalkChannel = "daily",
    msgtype: DingTalkMessageType = "markdown",
    timeout: float = 10.0,
) -> str:
    """Send a text or markdown message through a DingTalk robot webhook."""
    if channel not in ("test", "daily"):
        raise ValueError(f"Unsupported channel: {channel}. Expected 'test' or 'daily'.")
    if msgtype not in ("markdown", "text"):
        raise ValueError(f"Unsupported message type: {msgtype}. Expected 'markdown' or 'text'.")

    load_env()
    token_key = f"DING_{channel.upper()}_API_TOKEN"
    token = os.environ.get(token_key, "")
    if not token:
        raise ValueError(f"Missing required environment variable: {token_key}")

    url = f"https://oapi.dingtalk.com/robot/send?access_token={token}"
    if msgtype == "markdown":
        payload = {"msgtype": "markdown", "markdown": {"title": title, "text": text}}
    else:
        payload = {"msgtype": "text", "text": {"content": text}}

    response = httpx.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.text
