"""Flow composition module for FlowLLM.

This package provides base classes and helpers for constructing and executing
operation graphs (flows). It includes:

- BaseFlow: Abstract base providing sync/async execution and streaming support
- BaseToolFlow: BaseFlow variant that exposes a tool-call descriptor
- CmdFlow: Flow built from a user-provided expression string
- ExpressionToolFlow: Tool-enabled flow constructed from expression content

Common capabilities:
- Sequential and parallel composition via operator overloading
- Streaming and non-streaming responses
- Async and sync execution paths
- Structured error handling
"""

from .base_flow import BaseFlow
from .base_tool_flow import BaseToolFlow
from .cmd_flow import CmdFlow
from .expression_tool_flow import ExpressionToolFlow

__all__ = [
    "BaseFlow",
    "BaseToolFlow",
    "CmdFlow",
    "ExpressionToolFlow",
]
