"""Memory usage metrics for Prometheus monitoring."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prometheus_client import Gauge, Histogram

from gitingest.utils.memory_utils import get_memory_usage

if TYPE_CHECKING:
    import types
    from typing import Self

# Memory usage gauges
memory_usage_rss_mb = Gauge(
    "gitingest_memory_usage_rss_mb",
    "Resident Set Size memory usage in MB",
    ["repo_url"],
)

memory_usage_vms_mb = Gauge(
    "gitingest_memory_usage_vms_mb",
    "Virtual Memory Size usage in MB",
    ["repo_url"],
)

memory_usage_percent = Gauge(
    "gitingest_memory_usage_percent",
    "Memory usage percentage",
    ["repo_url"],
)

# Memory usage histogram to track distribution of memory consumption per repository
memory_consumption_histogram = Histogram(
    "gitingest_memory_consumption_mb",
    "Memory consumption distribution per repository in MB",
    ["repo_url"],
    buckets=(50, 100, 250, 500, 1000, 2000, 3000, 5000, 10000, float("inf")),
)

# Peak memory usage gauge
peak_memory_usage_mb = Gauge(
    "gitingest_peak_memory_usage_mb",
    "Peak memory usage during ingestion in MB",
    ["repo_url"],
)


def record_memory_usage(repo_url: str) -> dict[str, float]:
    """Record current memory usage metrics for a repository.

    Parameters
    ----------
    repo_url : str
        The repository URL to label the metrics with

    Returns
    -------
    dict[str, float]
        Current memory usage statistics

    """
    # Truncate URL for label to avoid excessive cardinality
    repo_label = repo_url[:255]

    # Get current memory stats
    memory_stats = get_memory_usage()

    # Record current memory usage
    memory_usage_rss_mb.labels(repo_url=repo_label).set(memory_stats["rss_mb"])
    memory_usage_vms_mb.labels(repo_url=repo_label).set(memory_stats["vms_mb"])
    memory_usage_percent.labels(repo_url=repo_label).set(memory_stats["percent"])

    # Record in histogram for distribution analysis
    memory_consumption_histogram.labels(repo_url=repo_label).observe(memory_stats["rss_mb"])

    return memory_stats


def record_peak_memory_usage(repo_url: str, peak_mb: float) -> None:
    """Record peak memory usage for a repository ingestion.

    Parameters
    ----------
    repo_url : str
        The repository URL to label the metrics with
    peak_mb : float
        Peak memory usage in MB

    """
    repo_label = repo_url[:255]
    peak_memory_usage_mb.labels(repo_url=repo_label).set(peak_mb)


class MemoryTracker:
    """Context manager to track memory usage during repository ingestion.

    Parameters
    ----------
    repo_url : str
        Repository URL for labeling metrics

    """

    def __init__(self, repo_url: str) -> None:
        self.repo_url = repo_url
        self.initial_memory = 0.0
        self.peak_memory = 0.0

    def __enter__(self) -> Self:
        """Start memory tracking."""
        initial_stats = get_memory_usage()
        self.initial_memory = initial_stats["rss_mb"]
        self.peak_memory = self.initial_memory

        # Record initial memory usage
        record_memory_usage(self.repo_url)

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """End memory tracking and record peak usage."""
        # Record final memory usage
        final_stats = record_memory_usage(self.repo_url)

        # Update peak if current is higher
        self.peak_memory = max(self.peak_memory, final_stats["rss_mb"])

        # Record peak memory usage
        record_peak_memory_usage(self.repo_url, self.peak_memory)

    def update_peak(self) -> None:
        """Update peak memory if current usage is higher."""
        current_stats = get_memory_usage()
        self.peak_memory = max(self.peak_memory, current_stats["rss_mb"])

        # Also record current usage
        record_memory_usage(self.repo_url)
