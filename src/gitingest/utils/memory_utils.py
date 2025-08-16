"""Memory utility functions for monitoring and optimization."""

from __future__ import annotations

import gc
from typing import Any

import psutil

from gitingest.utils.logging_config import get_logger

logger = get_logger(__name__)


def get_memory_usage() -> dict[str, Any]:
    """Get current memory usage statistics.

    Returns
    -------
    dict[str, Any]
        Dictionary containing memory usage statistics in MB.

    """
    try:
        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            "rss_mb": memory_info.rss / (1024 * 1024),  # Resident Set Size
            "vms_mb": memory_info.vms / (1024 * 1024),  # Virtual Memory Size
            "percent": process.memory_percent(),
        }
    except Exception as exc:
        logger.warning("Failed to get memory usage", extra={"error": str(exc)})
        return {"rss_mb": 0, "vms_mb": 0, "percent": 0}


def force_garbage_collection() -> None:
    """Force garbage collection to free up memory."""
    try:
        collected = gc.collect()
        logger.debug("Forced garbage collection", extra={"objects_collected": collected})
    except Exception as exc:
        logger.warning("Failed to force garbage collection", extra={"error": str(exc)})


def check_memory_pressure(threshold_mb: float = 2000) -> bool:
    """Check if memory usage is above threshold.

    Parameters
    ----------
    threshold_mb : float
        Memory threshold in MB (default: 3000 MB = 3 GB).

    Returns
    -------
    bool
        True if memory usage is above threshold.

    """
    memory_stats = get_memory_usage()
    return memory_stats["rss_mb"] > threshold_mb


def log_memory_stats(context: str = "") -> None:
    """Log current memory statistics.

    Parameters
    ----------
    context : str
        Context information for the log message.

    """
    memory_stats = get_memory_usage()
    logger.debug(
        "Memory usage statistics",
        extra={
            "context": context,
            "memory_rss_mb": round(memory_stats["rss_mb"], 2),
            "memory_vms_mb": round(memory_stats["vms_mb"], 2),
            "memory_percent": round(memory_stats["percent"], 2),
        },
    )
