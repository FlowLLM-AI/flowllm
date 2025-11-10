"""Configuration parser module for FlowLLM."""

from ..core.utils import PydanticConfigParser


class ConfigParser(PydanticConfigParser):
    """
    Configuration parser for FlowLLM framework.

    Extends PydanticConfigParser to provide configuration parsing capabilities
    with awareness of the current module location.
    """

    current_file: str = __file__
