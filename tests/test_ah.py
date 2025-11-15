"""Test module for AH download operation."""

from flowllm.extensions.data import AhDownloadOp
from flowllm.main import FlowLLMApp


def main():
    """Test the AH download operation."""
    with FlowLLMApp():
        AhDownloadOp().call()


if __name__ == "__main__":
    main()
