"""Context management module for FlowLLM.

This module provides context classes for managing application state,
flow execution, prompts, and class registries.

Exports:
    BaseContext: Base class for dictionary-like context management.
    FlowContext: Context for managing flow execution state and streaming.
    PromptHandler: Handler for loading and formatting prompts.
    Registry: Registry for storing and retrieving registered classes.
    ServiceContext: Singleton service context for global application state.
    C: Singleton instance of ServiceContext.
"""

from .base_context import BaseContext
from .flow_context import FlowContext
from .prompt_handler import PromptHandler
from .registry import Registry
from .service_context import C
from .service_context import ServiceContext

__all__ = [
    "BaseContext",
    "FlowContext",
    "PromptHandler",
    "Registry",
    "ServiceContext",
    "C",
]
