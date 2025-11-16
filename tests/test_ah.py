"""Test module for AH download operation."""

from flowllm.extensions.data import AhDownloadOp
from flowllm.extensions.data import AhFixOp
from flowllm.main import FlowLLMApp


def main():
    """Test the AH download operation."""

    _ = AhDownloadOp()
    op = AhFixOp()
    with FlowLLMApp():
        op.call()


if __name__ == "__main__":
    main()
