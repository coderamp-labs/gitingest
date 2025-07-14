"""Pattern utilities for the Gitingest package."""

from __future__ import annotations

import re
from typing import Iterable

from gitingest.utils.ignore_patterns import DEFAULT_IGNORE_PATTERNS

_PATTERN_SPLIT_RE = re.compile(r"[,\s]+")


def process_patterns(
    exclude_patterns: str | set[str] | None = None,
    include_patterns: str | set[str] | None = None,
) -> tuple[set[str], set[str] | None]:
    """Process include and exclude patterns.

    Parameters
    ----------
    exclude_patterns : str | set[str] | None
        Exclude patterns to process.
    include_patterns : str | set[str] | None
        Include patterns to process.

    Returns
    -------
    tuple[set[str], set[str] | None]
        A tuple containing the processed ignore patterns and include patterns.

    """
    # Combine default ignore patterns + custom patterns
    ignore_patterns_set = DEFAULT_IGNORE_PATTERNS.copy()
    if exclude_patterns:
        ignore_patterns_set.update(_parse_patterns(exclude_patterns))

    # Process include patterns and override ignore patterns accordingly
    if include_patterns:
        parsed_include = _parse_patterns(include_patterns)
        # Override ignore patterns with include patterns
        ignore_patterns_set = set(ignore_patterns_set) - set(parsed_include)
    else:
        parsed_include = None

    return ignore_patterns_set, parsed_include


def _parse_patterns(patterns: str | Iterable[str]) -> set[str]:
    """Normalize a collection of file or directory patterns.

    Parameters
    ----------
    patterns : str | Iterable[str]
        One pattern string or an iterable of pattern strings. Each pattern may contain multiple comma- or
        whitespace-separated sub-patterns, e.g. "src/*, tests *.md".

    Returns
    -------
    set[str]
        Normalized patterns with Windows back-slashes converted to forward-slashes and duplicates removed.

    """
    # Treat a lone string as the iterable [string]
    if isinstance(patterns, str):
        patterns = [patterns]

    # Flatten, split on commas/whitespace, strip empties, normalise slashes
    return {
        part.replace("\\", "/")
        for pat in patterns
        for part in _PATTERN_SPLIT_RE.split(pat.strip())
        if part  # discard empty tokens
    }
