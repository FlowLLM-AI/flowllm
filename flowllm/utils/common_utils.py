import os
import re
from pathlib import Path

from loguru import logger
from pyfiglet import Figlet
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def camel_to_snake(content: str) -> str:
    """
    BaseWorker -> base_worker
    """
    # FIXME
    content = content.replace("LLM", "Llm")

    snake_str = re.sub(r'(?<!^)(?=[A-Z])', '_', content).lower()
    return snake_str


def snake_to_camel(content: str) -> str:
    """
    base_worker -> BaseWorker
    """
    camel_str = "".join(x.capitalize() for x in content.split("_"))

    # FIXME
    camel_str = camel_str.replace("Llm", "LLM")
    return camel_str


def _load_env(path: Path):
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                continue

            line_split = line.strip().split("=", 1)
            if len(line_split) >= 2:
                key = line_split[0].strip()
                value = line_split[1].strip()
                os.environ[key] = value


def load_env(path: str | Path = None):
    if path is not None:
        path = Path(path)
        if path.exists():
            _load_env(path)

    else:
        for i in range(5):
            path = Path("../" * i + ".env")
            if path.exists():
                logger.info(f"using path={path}")
                _load_env(path)
                return

        logger.warning(".env not found")


def print_banner(name: str, service_config, width: int = 200):
    from flowllm.schema.service_config import ServiceConfig
    assert isinstance(service_config, ServiceConfig)

    f = Figlet(font="slant", width=width)
    logo: str = f.renderText(name)
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
            info_table.add_row("🔗", "URL:",
                               f"http://{service_config.mcp.host}:{service_config.mcp.port}/sse")

    info_table.add_row("", "", "")
    import flowllm
    info_table.add_row("🚀", "FlowLLM version:", Text(flowllm.__version__, style="dim white", no_wrap=True))
    import fastmcp
    info_table.add_row("📚", "FastMCP version:", Text(fastmcp.__version__, style="dim white", no_wrap=True))
    panel_content = Group(logo_text, "", info_table)

    panel = Panel(
        panel_content,
        title=name,
        title_align="left",
        border_style="dim",
        padding=(1, 4),
        expand=False,
    )

    console = Console(stderr=False)
    console.print(Group("\n", panel, "\n"))
