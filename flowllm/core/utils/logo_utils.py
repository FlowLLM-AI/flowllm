"""Logo and banner printing utilities.

This module provides utilities for printing styled logos and service information
using pyfiglet for ASCII art and rich for terminal formatting.
"""

from typing import TYPE_CHECKING

from pyfiglet import Figlet
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from ..schema import ServiceConfig


def print_logo(service_config: "ServiceConfig", app_name: str, width: int = 400):
    """Print a styled logo and service information banner.

    Creates and prints a formatted banner containing:
    - ASCII art logo generated from the app name
    - Service configuration information (backend, URL, transport)
    - Version information for FlowLLM and related dependencies

    Args:
        service_config: Service configuration object containing backend settings.
        app_name: Name of the application to display in the logo.
        width: Width for the ASCII art logo generation. Defaults to 400.

    The output is styled with colors and formatted as a panel using the rich library.
    """
    f = Figlet(font="slant", width=width)
    logo: str = f.renderText(app_name)
    logo_text = Text(logo, style="bold green")

    info_table = Table.grid(padding=(0, 1))
    info_table.add_column(style="bold", justify="center")  # Emoji column
    info_table.add_column(style="bold cyan", justify="left")  # Label column
    info_table.add_column(style="white", justify="left")  # Value column

    info_table.add_row("📦", "Backend:", service_config.backend)

    if service_config.backend == "http":
        info_table.add_row("🔗", "URL:", f"http://{service_config.http.host}:{service_config.http.port}")
    elif service_config.backend == "mcp":
        info_table.add_row("📚", "Transport:", service_config.mcp.transport)
        if service_config.mcp.transport == "sse":
            info_table.add_row(
                "🔗",
                "URL:",
                f"http://{service_config.mcp.host}:{service_config.mcp.port}/sse",
            )

    info_table.add_row("", "", "")
    import flowllm

    info_table.add_row("🚀", "FlowLLM version:", Text(flowllm.__version__, style="dim white", no_wrap=True))

    if service_config.backend == "http":
        import fastapi

        info_table.add_row("📚", "FastAPI version:", Text(fastapi.__version__, style="dim white", no_wrap=True))
    elif service_config.backend == "mcp":
        import fastmcp

        info_table.add_row("📚", "FastMCP version:", Text(fastmcp.__version__, style="dim white", no_wrap=True))
    panel_content = Group(logo_text, "", info_table)

    panel = Panel(
        panel_content,
        title=app_name,
        title_align="left",
        border_style="dim",
        padding=(1, 4),
        expand=False,
    )

    console = Console(stderr=False)
    console.print(Group("\n", panel, "\n"))
