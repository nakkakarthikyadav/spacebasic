"""
logger_setup.py
---------------
Configures rotating file + console logging for the SpaceBasic agent.
Call setup_logger() once at application start; every other module
then just uses:   logger = logging.getLogger("spacebasic")
"""

import logging
import logging.handlers
import os
from pathlib import Path


def setup_logger(log_dir: str = "logs", level: str = "INFO",
                 max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5) -> logging.Logger:
    """
    Set up a logger with both console and rotating-file handlers.

    Args:
        log_dir:       Directory where log files are stored.
        level:         Logging level string ("DEBUG", "INFO", etc.).
        max_bytes:     Max size of a single log file before rotation.
        backup_count:  How many old log files to keep.

    Returns:
        Configured Logger instance named "spacebasic".
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / "agent.log"

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger = logging.getLogger("spacebasic")
    logger.setLevel(numeric_level)

    # Avoid duplicate handlers when the module is re-imported
    if logger.handlers:
        return logger

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    logger.info("Logger initialised — writing to %s", log_file)
    return logger

