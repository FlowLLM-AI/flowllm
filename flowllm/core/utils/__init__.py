"""Utility modules for the flowllm core package.

This package provides utility functions and classes for:
- HTTP client operations for executing flows
- Common utility functions (string conversion, env loading, content extraction)
- MCP (Model Context Protocol) client operations
- LLM message formatting and processing utilities
- Timer utilities for measuring execution time
- Logger utilities for initializing and configuring loguru logger
- Logo and banner printing utilities
- Pydantic configuration parser for loading and merging configurations

Modules:
    http_client: Async HTTP client for executing flows with retry mechanism
    common_utils: Common utility functions for string conversion and content extraction
    fastmcp_client: Async MCP client using FastMCP for tool integration
    llm_utils: Utility functions for formatting and processing LLM messages
    timer: Timer class and decorator for measuring execution time
    logger_utils: Logger initialization utilities for loguru
    logo_utils: Logo and banner printing utilities using pyfiglet and rich
    pydantic_config_parser: Generic parser for Pydantic-based configuration management
    pydantic_utils: Utility functions for creating Pydantic models dynamically
"""

from .common_utils import (
    camel_to_snake,
    load_env,
    parse_flow_expression,
    singleton,
    snake_to_camel,
)
from .fastmcp_client import FastMcpClient
from .http_client import HttpClient
from .llm_utils import (
    extract_content,
    format_messages,
    merge_messages_content,
    parse_message_by_keys,
)
from .logger_utils import init_logger
from .logo_utils import print_logo
from .pydantic_config_parser import PydanticConfigParser
from .pydantic_utils import create_pydantic_model
from .timer import Timer, timer

__all__ = [
    "HttpClient",
    "FastMcpClient",
    "camel_to_snake",
    "snake_to_camel",
    "load_env",
    "extract_content",
    "parse_flow_expression",
    "singleton",
    "Timer",
    "timer",
    "init_logger",
    "print_logo",
    "create_pydantic_model",
    "PydanticConfigParser",
    "format_messages",
    "merge_messages_content",
    "parse_message_by_keys",
]
