"""Data package for FlowLLM framework.

This package provides data-related operations that can be used in LLM-powered flows.
It includes ready-to-use operations for:

- AhDownloadOp: Download AH stock data from Tushare API
"""

from .ah_download_op import AhDownloadOp

__all__ = [
    "AhDownloadOp",
]
