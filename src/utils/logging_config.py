"""
Logging configuration for Smart File Organizer.
Provides unified console, file, and in-memory activity logging with UI signal support.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, Optional

from src.utils.platform_utils import get_app_data_dir


class CallbackLogHandler(logging.Handler):
    """Logging handler that emits formatted log records to a Python callback or Qt signal."""

    def __init__(self, callback: Optional[Callable[[str, str], None]] = None):
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        if self.callback:
            try:
                msg = self.format(record)
                self.callback(record.levelname, msg)
            except Exception:
                pass


def setup_logging(
    log_file_name: str = "app.log",
    log_level: int = logging.INFO,
    callback: Optional[Callable[[str, str], None]] = None
) -> logging.Logger:
    """Configures application-wide logging."""
    logger = logging.getLogger("SmartFileOrganizer")
    logger.setLevel(log_level)

    # Avoid duplicate handlers on re-init
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    # 1. Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. Rotating file handler
    try:
        log_dir = get_app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_path = log_dir / log_file_name

        file_handler = RotatingFileHandler(
            str(file_path),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass

    # 3. UI callback handler
    if callback:
        cb_handler = CallbackLogHandler(callback)
        cb_handler.setFormatter(formatter)
        logger.addHandler(cb_handler)

    return logger
