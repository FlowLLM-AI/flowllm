import os
import sys
from datetime import datetime


def init_logger():
    from loguru import logger
    logger.remove()

    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    current_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    log_filename = f"{current_ts}.log"
    log_filepath = os.path.join(log_dir, log_filename)

    logger.add(log_filepath,
               level="INFO",
               rotation="00:00",
               retention="7 days",
               compression="zip",
               encoding="utf-8")

    logger.add(sink=sys.stdout,
               level="INFO",
               format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
               colorize=True)
