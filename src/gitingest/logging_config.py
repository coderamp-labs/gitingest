"""Global logger configuration."""

import logging
from typing import Literal

from pythonjsonlogger import jsonlogger


def setup_json_logging(level: Literal = logging.INFO) -> None:
    """Configure json logger for the whole gitingest module."""
    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    log_handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    log_handler.setFormatter(formatter)
    logger.handlers = [log_handler]
