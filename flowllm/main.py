"""Main entry point for FlowLLM application."""

import sys

from .core.app import FlowLLMApp
from .config import ConfigParser


def main():
    """
    Main entry point for FlowLLM application.

    Initializes the FlowLLM application with command-line arguments and runs the service.
    """
    with FlowLLMApp(*sys.argv[1:], parser=ConfigParser) as app:
        app.run_service()


if __name__ == "__main__":
    main()
