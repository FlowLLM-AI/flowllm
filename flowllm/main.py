"""Main entry point for FlowLLM application."""

import sys

from .config import ConfigParser
from .core.application import Application


class FlowLLMApp(Application):
    """
    Convenience application class for FlowLLM framework.

    This class extends Application to provide a simplified interface with
    default configurations. It automatically uses ConfigParser and loads
    the default configuration file (default.yaml) if no custom config_path
    is provided.

    This is the recommended entry point for most FlowLLM applications.
    For advanced use cases requiring custom parsers or configurations,
    use Application directly instead.
    """

    def __init__(
        self,
        *args,
        llm_api_key: str = None,
        llm_api_base: str = None,
        embedding_api_key: str = None,
        embedding_api_base: str = None,
        config_path: str = None,
        **kwargs,
    ):
        """
        Initialize FlowLLMApp with default configurations.

        Args:
            *args: Additional arguments passed to ConfigParser. Examples:
                - "llm.default.model_name=qwen3-30b-a3b-thinking-2507"
                - "llm.default.backend=openai_compatible"
                - "llm.default.params={'temperature': '0.6'}"
                - "embedding_model.default.model_name=text-embedding-v4"
                - "embedding_model.default.backend=openai_compatible"
                - "embedding_model.default.params={'dimensions': 1024}"
                - "vector_store.default.backend=memory"
                - "vector_store.default.embedding_model=default"
                - "vector_store.default.params={...}"
            llm_api_key: API key for LLM service
            llm_api_base: Base URL for LLM API
            embedding_api_key: API key for embedding service
            embedding_api_base: Base URL for embedding API
            config_path: Path to custom configuration YAML file. If provided, loads
                configuration from this file. If None, loads default.yaml automatically.
            **kwargs: Additional keyword arguments passed to ConfigParser.
        """
        super().__init__(
            *args,
            llm_api_key=llm_api_key,
            llm_api_base=llm_api_base,
            embedding_api_key=embedding_api_key,
            embedding_api_base=embedding_api_base,
            service_config=None,
            parser=ConfigParser,
            config_path=config_path,
            load_default_config=True,
            **kwargs,
        )


def main():
    """
    Main entry point for FlowLLM application.

    Initializes FlowLLMApp with command-line arguments and runs the service.
    This function is typically called when running FlowLLM from the command line.

    Usage:
        flowllm [config_path] [additional_config_overrides...]

    Example:
        flowllm config=my_config.yaml llm.default.model_name=qwen3-max

    conda create -n fl_test python=3.10
    conda activate fl_test
    conda env remove -n fl_test
    """
    with FlowLLMApp(*sys.argv[1:]) as app:
        app.run_service()


if __name__ == "__main__":
    main()
