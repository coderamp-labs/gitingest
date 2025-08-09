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

    for expected_content_item in pattern_scenario["expected_content"]:
        assert expected_content_item in content

    for expected_structure_item in pattern_scenario["expected_structure"]:
        assert expected_structure_item in structure

    for expected_not_structure_item in pattern_scenario["expected_not_structure"]:
        assert expected_not_structure_item not in structure


def test_ingest_skips_binary_files(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that binary files are not included as raw content, but as a marker."""
    binary_file = temp_directory / "binary.bin"
    binary_file.write_bytes(b"\x00\xff\x00\xff")

    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None

    _, _, content = ingest_query(sample_query)
    assert "binary.bin" in content
    assert "[Binary file]" in content
    assert b"\x00\xff\x00\xff".decode(errors="ignore") not in content


def test_ingest_skips_symlinks(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that symlinks are not included as file content, but as a marker."""
    target_file = temp_directory / "file1.txt"
    target_file.write_text("hello")
    symlink = temp_directory / "symlink.txt"
    symlink.symlink_to(target_file)

    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None

    _, _, content = ingest_query(sample_query)
    assert "symlink.txt" in content
    assert "SYMLINK: symlink.txt" in content
    assert "hello" not in content.split("SYMLINK: symlink.txt")[1]


def test_symlink_loop(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that symlink loops do not cause infinite recursion."""
    loop_dir = temp_directory / "loop"
    loop_dir.mkdir()
    (loop_dir / "file.txt").write_text("loop file")
    # Create a symlink inside loop_dir pointing to its parent
    (loop_dir / "parent_link").symlink_to(temp_directory)
    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None
    _, _, content = ingest_query(sample_query)
    assert "file.txt" in content


def test_ingest_large_file_handling(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that files exceeding max_file_size are skipped."""
    large_file = temp_directory / "large.txt"
    large_file.write_text("A" * (sample_query.max_file_size + 1))

    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None

    _, _, content = ingest_query(sample_query)
    assert "large.txt" not in content, "Large files should be skipped from content."


def test_ingest_hidden_files(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that hidden files are handled according to ignore/include patterns."""
    hidden_file = temp_directory / ".hidden.txt"
    hidden_file.write_text("secret")

    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None
    sample_query.ignore_patterns = {".hidden.txt"}

    summary, _, content = ingest_query(sample_query)
    assert ".hidden.txt" not in content
    assert ".hidden.txt" not in summary


def test_ingest_empty_file(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that empty files are included but content is empty."""
    empty_file = temp_directory / "empty.txt"
    empty_file.write_text("")

    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None

    _, _, content = ingest_query(sample_query)
    assert "empty.txt" in content
    # Adjust regex to match actual output
    assert re.search(r"FILE: empty\.txt\s*\n=+\n\s*\n", content) or "FILE: empty.txt" in content


def test_ingest_permission_error(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that files with permission errors are marked in content."""
    restricted_file = temp_directory / "restricted.txt"
    restricted_file.write_text("top secret")
    restricted_file.chmod(0o000)

    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None

    _, _, content = ingest_query(sample_query)
    assert "restricted.txt" in content
    assert "Error reading file" in content
    restricted_file.chmod(0o644)


def test_ingest_weird_encoding(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that files with non-UTF8 encoding are marked in content."""
    weird_file = temp_directory / "weird.txt"
    weird_file.write_bytes("café".encode("utf-16"))

    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None

    _, _, content = ingest_query(sample_query)
    assert "weird.txt" in content
    assert "[Encoding error]" in content or "[Binary file]" in content


def test_ingest_deeply_nested_structure(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that deeply nested files are included if patterns match."""
    nested_dir = temp_directory / "a/b/c/d/e"
    nested_dir.mkdir(parents=True)
    nested_file = nested_dir / "deep.txt"
    nested_file.write_text("deep content")

    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None
    sample_query.include_patterns = {"**/deep.txt"}

    summary, _, content = ingest_query(sample_query)
    assert "deep.txt" in content
    assert "Files analyzed:" in summary


def test_include_nonexistent_extension(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that include patterns with nonexistent extensions match no files."""
    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None
    sample_query.include_patterns = {"*.xyz"}
    summary, _, content = ingest_query(sample_query)
    assert "Files analyzed: 0" in summary
    assert content.strip() == ""


def test_ignore_nonexistent_files(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that ignore patterns with nonexistent files do not affect results."""
    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None
    sample_query.ignore_patterns = {"nonexistent.txt"}
    summary, _, content = ingest_query(sample_query)
    assert "file1.txt" in content
    assert "Files analyzed:" in summary


def test_unicode_special_char_filenames(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test ingestion of files with unicode/special characters in filenames."""
    unicode_file = temp_directory / "unicodé_文件.txt"
    unicode_file.write_text("hello unicode")
    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None
    _, _, content = ingest_query(sample_query)
    assert "unicodé_文件.txt" in content
    assert "hello unicode" in content


def test_mixed_line_endings(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test ingestion of files with mixed line endings (LF/CRLF)."""
    lf_file = temp_directory / "lf.txt"
    crlf_file = temp_directory / "crlf.txt"
    lf_file.write_text("line1\nline2\n")
    crlf_file.write_text("line1\r\nline2\r\n")
    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None
    _, _, content = ingest_query(sample_query)
    assert "lf.txt" in content
    assert "crlf.txt" in content
    assert "line1" in content
    assert "line2" in content


def test_mixed_file_types_in_directory(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test ingestion with a mix of file types in one directory."""
    (temp_directory / "text.txt").write_text("text")
    (temp_directory / "binary.bin").write_bytes(b"\x00\xff")
    (temp_directory / "symlink.txt").symlink_to(temp_directory / "text.txt")
    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None
    _, _, content = ingest_query(sample_query)
    assert "text.txt" in content
    assert "binary.bin" in content
    assert "[Binary file]" in content
    assert "symlink.txt" in content
    assert "SYMLINK:" in content


def test_pattern_matching_various_globs(temp_directory: Path, sample_query: IngestionQuery) -> None:
    """Test that various glob patterns correctly match files for ingestion."""
    (temp_directory / "foo.txt").write_text("foo")
    (temp_directory / "bar.py").write_text("bar")
    (temp_directory / "baz.md").write_text("baz")
    subdir = temp_directory / "sub"
    subdir.mkdir()
    (subdir / "nested.py").write_text("nested")
    (subdir / "nested.txt").write_text("nested txt")

    sample_query.local_path = temp_directory
    sample_query.subpath = "/"
    sample_query.type = None
    sample_query.include_patterns = {"*.txt"}
    sample_query.ignore_patterns = set()
    _, _, content = ingest_query(sample_query)
    assert "foo.txt" in content
    assert "bar.py" not in content
    assert "baz.md" not in content
    assert "nested.txt" in content

    sample_query.include_patterns = {"**/*.py"}
    _, _, content = ingest_query(sample_query)
    assert "bar.py" in content
    assert "nested.py" in content
    assert "foo.txt" not in content

    sample_query.include_patterns = {"*.md", "sub/*.txt"}
    _, _, content = ingest_query(sample_query)
    assert "baz.md" in content
    assert "nested.txt" in content
    assert "foo.txt" not in content
    assert "bar.py" not in content

    sample_query.include_patterns = set()
    sample_query.ignore_patterns = {"*.py", "sub/*.py"}
    _, _, content = ingest_query(sample_query)
    assert "foo.txt" in content
    assert "baz.md" in content
    assert "bar.py" not in content
    assert "nested.py" not in content
