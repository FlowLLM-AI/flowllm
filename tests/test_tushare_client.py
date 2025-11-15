"""Test module for Tushare client."""

from loguru import logger

from flowllm.core.utils import TushareClient
from flowllm.main import FlowLLMApp


def main():
    """Test the Tushare client by requesting daily data."""
    with FlowLLMApp():
        client = TushareClient()
        df = client.request(api_name="daily", ts_code="000001.SZ")
        logger.info(df)


if __name__ == "__main__":
    main()
