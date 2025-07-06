"""Test pattern utilities."""

import pytest

from gitingest.utils.ignore_patterns import DEFAULT_IGNORE_PATTERNS
from gitingest.utils.pattern_utils import _parse_patterns, process_patterns


def test_process_patterns_empty_patterns() -> None:
    """Test ``process_patterns`` with empty patterns.

    Given empty ``include_patterns`` and ``exclude_patterns``:
    When ``process_patterns`` is called,
    Then ``include_patterns`` becomes ``None`` and ``DEFAULT_IGNORE_PATTERNS`` apply.
    """
    exclude_patterns, include_patterns = process_patterns(exclude_patterns="", include_patterns="")

    assert include_patterns is None
    assert exclude_patterns == DEFAULT_IGNORE_PATTERNS


def test_parse_patterns_valid() -> None:
    """Test ``_parse_patterns`` with valid comma-separated patterns.

    Given patterns like "*.py, *.md, docs/*":
    When ``_parse_patterns`` is called,
    Then it should return a set of parsed strings.
    """
    patterns = "*.py, *.md, docs/*"
    parsed_patterns = _parse_patterns(patterns)

    assert parsed_patterns == {"*.py", "*.md", "docs/*"}


def test_parse_patterns_invalid_characters() -> None:
    """Test ``_parse_patterns`` with invalid characters.

    Given a pattern string containing special characters (e.g. "*.py;rm -rf"):
    When ``_parse_patterns`` is called,
    Then a ValueError should be raised indicating invalid pattern syntax.
    """
    patterns = "*.py;rm -rf"

    with pytest.raises(ValueError, match="Pattern.*contains invalid characters"):
        _parse_patterns(patterns)


def test_process_patterns_include_and_ignore_overlap() -> None:
    """Test ``process_patterns`` with overlapping patterns.

    Given include="*.py" and ignore={"*.py", "*.txt"}:
    When ``process_patterns`` is called,
    Then "*.py" should be removed from ignore patterns.
    """
    exclude_patterns, include_patterns = process_patterns(exclude_patterns={"*.py", "*.txt"}, include_patterns="*.py")

    assert include_patterns == {"*.py"}
    assert exclude_patterns is not None
    assert "*.py" not in exclude_patterns
    assert "*.txt" in exclude_patterns
