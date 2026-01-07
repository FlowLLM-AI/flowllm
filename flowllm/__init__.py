"""FlowLLM: A library for managing LLM flows and contexts."""

import os

os.environ.setdefault("FLOW_APP_NAME", "FlowLLM")

from .core.utils import load_env  # noqa: E402  # pylint: disable=wrong-import-position

load_env()

from . import gallery  # noqa: E402, F401  # pylint: disable=wrong-import-position,unused-import
# from . import extensions  # noqa: E402, F401  # pylint: disable=wrong-import-position,unused-import

__version__ = "0.2.0.10"
