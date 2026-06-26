"""Startup banner."""

import colorsys
import importlib.metadata
import random
from typing import TYPE_CHECKING

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from ..schema import ApplicationConfig


def _get_version(package_name: str) -> str:
    """Return installed package version or empty string."""
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return ""


def _hsv_rgb(h: float, s: float = 0.85, v: float = 0.98) -> tuple[int, int, int]:
    """HSV → 0-255 RGB tuple."""
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def print_logo(app_config: "ApplicationConfig"):
    """Print rainbow ASCII logo and runtime config."""
    ascii_art = [
        r" ███████╗ ██╗      ██████╗  ██╗    ██╗ ██╗      ██╗      ███╗   ███╗ ",
        r" ██╔════╝ ██║     ██╔═══██╗ ██║    ██║ ██║      ██║      ████╗ ████║ ",
        r" █████╗   ██║     ██║   ██║ ██║ █╗ ██║ ██║      ██║      ██╔████╔██║ ",
        r" ██╔══╝   ██║     ██║   ██║ ██║███╗██║ ██║      ██║      ██║╚██╔╝██║ ",
        r" ██║      ███████╗╚██████╔╝ ╚███╔███╔╝ ███████╗ ███████╗ ██║ ╚═╝ ██║ ",
        r" ╚═╝      ╚══════╝ ╚═════╝   ╚══╝╚══╝  ╚══════╝ ╚══════╝ ╚═╝     ╚═╝ ",
    ]

    hue_base = random.random()  # random starting hue per startup
    horizontal_span = 0.5  # half the wheel left-to-right
    vertical_shift = 0.08  # small per-line nudge for 2D rainbow

    logo_text = Text()
    for line_idx, line in enumerate(ascii_art):
        line_len = max(1, len(line) - 1)
        line_hue_start = hue_base + line_idx * vertical_shift
        for i, char in enumerate(line):
            ratio = i / line_len
            r, g, b = _hsv_rgb(line_hue_start + horizontal_span * ratio)
            logo_text.append(char, style=f"bold rgb({r},{g},{b})")
        logo_text.append("\n")

    info_table = Table.grid(padding=(0, 1))
    info_table.add_column(style="bold", justify="center")
    info_table.add_column(style="bold cyan", justify="left")
    info_table.add_column(style="white", justify="left")

    # Backend-specific fields live in model_extra.
    service = app_config.service
    backend = service.backend
    extra = service.model_extra or {}

    info_table.add_row("📦", "Backend:", backend)

    match backend:
        case "http":
            host = extra.get("host", "localhost")
            port = extra.get("port", 8000)
            info_table.add_row("🔗", "URL:", f"http://{host}:{port}")
            info_table.add_row("📚", "FastAPI:", Text(_get_version("fastapi"), style="dim"))
        case "mcp":
            transport = extra.get("transport", "stdio")
            info_table.add_row("🚌", "Transport:", transport)
            if transport != "stdio":
                host = extra.get("host", "localhost")
                port = extra.get("port", 8000)
                url = f"http://{host}:{port}"
                if transport == "sse":
                    url += "/sse"
                info_table.add_row("🔗", "URL:", url)
            info_table.add_row("📚", "FastMCP:", Text(_get_version("fastmcp"), style="dim"))

    info_table.add_row("🚀", "FlowLLM:", Text(_get_version("flowllm"), style="dim"))

    panel = Panel(
        Group(logo_text, info_table),
        title=app_config.app_name,
        title_align="left",
        border_style="dim",
        padding=(1, 4),
        expand=False,
    )

    Console().print(Group("\n", panel, "\n"))
