"""Logger utilities for initializing and configuring loguru logger.

This module provides utilities for setting up loguru logger with file and console outputs,
including automatic log rotation, retention, and compression.
"""

import os
import sys
from datetime import datetime


def init_logger(log_dir: str = "logs", level: str = "INFO"):
    """Initialize and configure the loguru logger.

    Sets up loguru logger with two sinks:
    1. File sink: Logs are written to files in the specified directory with rotation,
       retention, and compression settings.
    2. Console sink: Logs are also output to stdout with colorization.

    Args:
        log_dir: Directory path where log files will be stored. Defaults to "logs".
        level: Logging level (e.g., "INFO", "DEBUG", "WARNING", "ERROR"). Defaults to "INFO".

    Note:
        The log filename is automatically generated using the current timestamp
        in the format "YYYY-MM-DD_HH-MM-SS.log".
        Files are rotated at midnight, retained for 7 days, and compressed as zip.
    """
    from loguru import logger

    logger.remove()
    os.makedirs(log_dir, exist_ok=True)

    current_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    log_filename = f"{current_ts}.log"
    log_filepath = os.path.join(log_dir, log_filename)

    logger.add(
        log_filepath,
        level=level,
        rotation="00:00",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{line} | {message}",
    )

    logger.add(
        sink=sys.stdout,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{line} | {message}",
        colorize=True,
    )
