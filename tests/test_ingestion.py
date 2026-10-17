"""Tests for the ``query_ingestion`` module.

These tests validate directory scanning, file content extraction, notebook handling, and the overall ingestion logic,
including filtering patterns and subpaths.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, TypedDict

import pytest

from gitingest.ingestion import ingest_query

if TYPE_CHECKING:
    from pathlib import Path

    from gitingest.query_parser import IngestionQuery


def test_run_ingest_query(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test ``ingest_query`` to ensure it processes the directory and returns expected results.

    Given a directory with ``.txt`` and ``.py`` files:
    When ``ingest_query`` is invoked,
    Then it should produce a summary string listing the files analyzed and a combined content string.
    """
    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None

    summary, _, content = ingest_query(sample_query)

    assert "Repository: test_user/test_repo" in summary
    assert "Files analyzed: 8" in summary

    # Check presence of key files in the content
    assert "src/subfile1.txt" in content
    assert "src/subfile2.py" in content
    assert "src/subdir/file_subdir.txt" in content
    assert "src/subdir/file_subdir.py" in content
    assert "file1.txt" in content
    assert "file2.py" in content
    assert "dir1/file_dir1.txt" in content
    assert "dir2/file_dir2.txt" in content


# TODO: Additional tests:
# - Multiple include patterns, e.g. ["*.txt", "*.py"] or ["/src/*", "*.txt"].
# - Edge cases with weird file names or deep subdirectory structures.
# TODO : def test_include_nonexistent_extension


class PatternScenario(TypedDict):
    """A scenario for testing the ingestion of a set of patterns."""

    include_patterns: set[str]
    ignore_patterns: set[str]
    expected_num_files: int
    expected_content: set[str]
    expected_structure: set[str]
    expected_not_structure: set[str]


@pytest.mark.parametrize(
    "pattern_scenario",
    [
        pytest.param(
            PatternScenario(
                {
                    "include_patterns": {"file2.py", "dir2/file_dir2.txt"},
                    "ignore_patterns": {*()},
                    "expected_num_files": 2,
                    "expected_content": {"file2.py", "dir2/file_dir2.txt"},
                    "expected_structure": {"test_repo/", "dir2/"},
                    "expected_not_structure": {"src/", "subdir/", "dir1/"},
                },
            ),
            id="include-explicit-files",
        ),
        pytest.param(
            PatternScenario(
                {
                    "include_patterns": {
                        "file1.txt",
                        "file2.py",
                        "file_dir1.txt",
                        "*/file_dir2.txt",
                    },
                    "ignore_patterns": {*()},
                    "expected_num_files": 4,
                    "expected_content": {"file1.txt", "file2.py", "dir1/file_dir1.txt", "dir2/file_dir2.txt"},
                    "expected_structure": {"test_repo/", "dir1/", "dir2/"},
                    "expected_not_structure": {"src/", "subdir/"},
                },
            ),
            id="include-wildcard-directory",
        ),
        pytest.param(
            PatternScenario(
                {
                    "include_patterns": {"*.py"},
                    "ignore_patterns": {*()},
                    "expected_num_files": 3,
                    "expected_content": {
                        "file2.py",
                        "src/subfile2.py",
                        "src/subdir/file_subdir.py",
                    },
                    "expected_structure": {"test_repo/", "src/", "subdir/"},
                    "expected_not_structure": {"dir1/", "dir2/"},
                },
            ),
            id="include-wildcard-files",
        ),
        pytest.param(
            PatternScenario(
                {
                    "include_patterns": {"**/file_dir2.txt", "src/**/*.py"},
                    "ignore_patterns": {*()},
                    "expected_num_files": 3,
                    "expected_content": {
                        "dir2/file_dir2.txt",
                        "src/subfile2.py",
                        "src/subdir/file_subdir.py",
                    },
                    "expected_structure": {"test_repo/", "dir2/", "src/", "subdir/"},
                    "expected_not_structure": {"dir1/"},
                },
            ),
            id="include-recursive-wildcard",
        ),
        pytest.param(
            PatternScenario(
                {
                    "include_patterns": {*()},
                    "ignore_patterns": {"file2.py", "dir2/file_dir2.txt"},
                    "expected_num_files": 6,
                    "expected_content": {
                        "file1.txt",
                        "src/subfile1.txt",
                        "src/subfile2.py",
                        "src/subdir/file_subdir.txt",
                        "src/subdir/file_subdir.py",
                        "dir1/file_dir1.txt",
                    },
                    "expected_structure": {"test_repo/", "src/", "subdir/", "dir1/"},
                    "expected_not_structure": {"dir2/"},
                },
            ),
            id="exclude-explicit-files",
        ),
        pytest.param(
            PatternScenario(
                {
                    "include_patterns": {*()},
                    "ignore_patterns": {"file1.txt", "file2.py", "*/file_dir1.txt"},
                    "expected_num_files": 5,
                    "expected_content": {
                        "src/subfile1.txt",
                        "src/subfile2.py",
                        "src/subdir/file_subdir.txt",
                        "src/subdir/file_subdir.py",
                        "dir2/file_dir2.txt",
                    },
                    "expected_structure": {"test_repo/", "src/", "subdir/", "dir2/"},
                    "expected_not_structure": {"dir1/"},
                },
            ),
            id="exclude-wildcard-directory",
        ),
        pytest.param(
            PatternScenario(
                {
                    "include_patterns": {*()},
                    "ignore_patterns": {"src/**/*.py"},
                    "expected_num_files": 6,
                    "expected_content": {
                        "file1.txt",
                        "file2.py",
                        "src/subfile1.txt",
                        "src/subdir/file_subdir.txt",
                        "dir1/file_dir1.txt",
                        "dir2/file_dir2.txt",
                    },
                    "expected_structure": {
                        "test_repo/",
                        "dir1/",
                        "dir2/",
                        "src/",
                        "subdir/",
                    },
                    "expected_not_structure": {*()},
                },
            ),
            id="exclude-recursive-wildcard",
        ),
    ],
)
def test_include_ignore_patterns(
    temp_directory: Path,
    sample_query: IngestionQuery,
    pattern_scenario: PatternScenario,
) -> None:
    """Test ``ingest_query`` to ensure included and ignored paths are included and ignored respectively.

    Given a directory with ``.txt`` and ``.py`` files, and a set of include patterns or a set of ignore patterns:
    When ``ingest_query`` is invoked,
    Then it should produce a summary string listing the files analyzed and a combined content string.
    """
    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None
    sample_query.include_patterns = pattern_scenario["include_patterns"]
    sample_query.ignore_patterns = pattern_scenario["ignore_patterns"]

    summary, structure, content = ingest_query(sample_query)

    assert "Repository: test_user/test_repo" in summary
    num_files_regex = re.compile(r"^Files analyzed: (\d+)$", re.MULTILINE)
    assert (num_files_match := num_files_regex.search(summary)) is not None
    assert int(num_files_match.group(1)) == pattern_scenario["expected_num_files"]

    # Check presence of key files in the content
    for expected_content_item in pattern_scenario["expected_content"]:
        assert expected_content_item in content

    # check presence of included directories in structure
    for expected_structure_item in pattern_scenario["expected_structure"]:
        assert expected_structure_item in structure

    # check non-presence of non-included directories in structure
    for expected_not_structure_item in pattern_scenario["expected_not_structure"]:
        assert expected_not_structure_item not in structure


def test_ingest_query_single_file_max_file_size_exceeded(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that ingesting a single file exceeding max_file_size raises ValueError."""
    file_path = temp_directory / "large_file.txt"
    file_path.write_text("A" * 500, encoding="utf-8")

    sample_query.local_path = file_path
    sample_query.subpath = "/"
    sample_query.type = None
    sample_query.max_file_size = 50

    with pytest.raises(ValueError, match="exceeds the maximum allowed file size"):
        ingest_query(sample_query)


def test_ingest_query_single_file_within_max_file_size(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that ingesting a single file within max_file_size succeeds."""
    file_path = temp_directory / "small_file.txt"
    file_path.write_text("Hello world", encoding="utf-8")

    sample_query.local_path = file_path
    sample_query.subpath = "/"
    sample_query.type = None
    sample_query.max_file_size = 500

    summary, structure, content = ingest_query(sample_query)
    assert "File: small_file.txt" in summary
    assert "small_file.txt" in structure
    assert "Hello world" in content
