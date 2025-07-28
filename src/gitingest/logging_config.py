"""Global logger configuration."""

import logging
import os
from typing import Literal

from pythonjsonlogger import jsonlogger


def setup_logging(level: Literal = logging.INFO) -> None:
    """Configure logger for the whole gitingest module.

    Selects formatter based on LOG_FORMAT env variable:
    - 'json': JSON formatter (time/level/msg, then extras)
    - any other value or unset: default formatter
    """
    logger = logging.getLogger()
    logger.setLevel(level)
    log_handler = logging.StreamHandler()

    log_format = os.getenv("LOG_FORMAT", "default").lower()
    if log_format == "json":
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(message)s %(name)s %(module)s %(funcName)s %(lineno)d",
        )
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log_handler.setFormatter(formatter)
    logger.handlers = [log_handler]
