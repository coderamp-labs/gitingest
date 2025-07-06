"""Pattern utilities for the Gitingest package."""

from __future__ import annotations

import re

from gitingest.utils.exceptions import InvalidPatternError
from gitingest.utils.ignore_patterns import DEFAULT_IGNORE_PATTERNS


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


def _parse_patterns(pattern: set[str] | str) -> set[str]:
    """Parse and validate file/directory patterns for inclusion or exclusion.

    Takes either a single pattern string or set of pattern strings and processes them into a normalized list.
    Patterns are split on commas and spaces, validated for allowed characters, and normalized.

    Parameters
    ----------
    pattern : set[str] | str
        Pattern(s) to parse - either a single string or set of strings

    Returns
    -------
    set[str]
        A set of normalized patterns.

    Raises
    ------
    InvalidPatternError
        If any pattern contains invalid characters. Only alphanumeric characters,
        dash (-), underscore (_), dot (.), forward slash (/), plus (+), and
        asterisk (*) are allowed.

    """
    patterns = pattern if isinstance(pattern, set) else {pattern}

    parsed_patterns: set[str] = set()
    for p in patterns:
        parsed_patterns = parsed_patterns.union(set(re.split(",| ", p)))

    # Remove empty string if present
    parsed_patterns = parsed_patterns - {""}

    # Normalize Windows paths to Unix-style paths
    parsed_patterns = {p.replace("\\", "/") for p in parsed_patterns}

    # Validate and normalize each pattern
    for p in parsed_patterns:
        if not _is_valid_pattern(p):
            raise InvalidPatternError(p)

    return parsed_patterns


def _is_valid_pattern(pattern: str) -> bool:
    """Validate if the given pattern contains only valid characters.

    This function checks if the pattern contains only alphanumeric characters or one
    of the following allowed characters: dash ('-'), underscore ('_'), dot ('.'),
    forward slash ('/'), plus ('+'), asterisk ('*'), or the at sign ('@').

    Parameters
    ----------
    pattern : str
        The pattern to validate.

    Returns
    -------
    bool
        ``True`` if the pattern is valid, otherwise ``False``.

    """
    return all(c.isalnum() or c in "-_./+*@" for c in pattern)
