"""Logging configuration for gitingest using loguru.

This module provides structured JSON logging suitable for Kubernetes deployments
while also supporting human-readable logging for development.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

from loguru import logger


def json_sink(message: Any) -> None:  # noqa: ANN401
    """Create JSON formatted log output.

    Parameters
    ----------
    message : Any
        The loguru message record

    """
    record = message.record

    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name.upper(),
        "logger": record["name"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "message": record["message"],
    }

    # Add exception info if present
    if record["exception"]:
        log_entry["exception"] = {
            "type": record["exception"].type.__name__,
            "value": str(record["exception"].value),
            "traceback": record["exception"].traceback,
        }

    # Add extra fields if present
    if record["extra"]:
        log_entry.update(record["extra"])

    sys.stdout.write(json.dumps(log_entry, ensure_ascii=False, separators=(",", ":")) + "\n")


class InterceptHandler(logging.Handler):
    """Intercept standard library logging and redirect to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record to loguru."""
        # Get corresponding loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


def configure_logging() -> None:
    """Configure loguru for the application.

    Sets up JSON logging for production/Kubernetes environments
    or human-readable logging for development.
    Intercepts all standard library logging including uvicorn.
    """
    # Remove default handler
    logger.remove()

    # Check if we're in Kubernetes or production environment
    is_k8s = os.getenv("KUBERNETES_SERVICE_HOST") is not None
    log_format = os.getenv("LOG_FORMAT", "json" if is_k8s else "human")
    log_level = os.getenv("LOG_LEVEL", "INFO")

    if log_format.lower() == "json":
        # JSON format for structured logging (Kubernetes/production)
        logger.add(
            json_sink,
            level=log_level,
            enqueue=True,  # Async logging for better performance
            diagnose=False,  # Don't include variable values in exceptions (security)
            backtrace=True,  # Include full traceback
            serialize=True,  # Ensure proper serialization
        )
    else:
        # Human-readable format for development
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>",
            level=log_level,
            enqueue=True,
            diagnose=True,  # Include variable values in development
            backtrace=True,
        )

    # Intercept all standard library logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Intercept specific loggers that might bypass basicConfig
    for name in logging.root.manager.loggerDict:  # pylint: disable=no-member
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True


def get_logger(name: str | None = None) -> logger.__class__:
    """Get a configured logger instance.

    Parameters
    ----------
    name : str | None, optional
        Logger name, defaults to the calling module name

    Returns
    -------
    logger.__class__
        Configured logger instance

    """
    if name:
        return logger.bind(name=name)
    return logger


# Initialize logging when module is imported
configure_logging()
