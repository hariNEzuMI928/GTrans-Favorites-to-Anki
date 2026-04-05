import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Union

from . import config


def setup_logging() -> None:
    # Ensure data directory exists for logs
    log_path: Path = config.APP_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger: logging.Logger = logging.getLogger()

    # Clear previous handlers to prevent duplicate logs if setup_logging is called multiple times
    # Iterate over a copy of the list to avoid issues when modifying it
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create formatter
    formatter: logging.Formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    file_handler: RotatingFileHandler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)

    # Console handler
    stream_handler: logging.StreamHandler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    # Set logging level from config
    # Use getattr to safely get the logging level constant
    log_level: Union[int, str] = getattr(logging, config.LOG_LEVEL, logging.INFO)
    root_logger.setLevel(log_level)

    # Add handlers to root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
