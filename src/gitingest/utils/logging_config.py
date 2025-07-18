"""Centralized logging configuration for JSON logging in k8s environments."""

from __future__ import annotations

import json
import logging
import sys


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry)


def configure_json_logging(level: str = "INFO") -> None:
    """Configure JSON logging for the application.

    Parameters
    ----------
    level : str
        Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create JSON formatter
    formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler for stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Parameters
    ----------
    name : str
        Logger name (typically __name__)

    Returns
    -------
    logging.Logger
        Configured logger instance

    """
    return logging.getLogger(name)


def log_with_extra(logger: logging.Logger, level: str, message: str, **extra_fields: str | int | bool | None) -> None:
    """Log a message with extra fields.

    Parameters
    ----------
    logger : logging.Logger
        Logger instance
    level : str
        Log level (debug, info, warning, error, critical)
    message : str
        Log message
    **extra_fields : str | int | bool | None
        Additional fields to include in the log entry

    """
    # Create a LogRecord with extra fields
    record = logger.makeRecord(
        logger.name,
        getattr(logging, level.upper()),
        "",
        0,
        message,
        (),
        None,
    )
    record.extra_fields = extra_fields
    logger.handle(record)
