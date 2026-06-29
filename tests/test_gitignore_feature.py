"""Tests for the gitignore functionality in Gitingest."""

from pathlib import Path

import pytest

from gitingest.entrypoint import ingest_async
from gitingest.utils.ignore_patterns import load_ignore_patterns


@pytest.fixture(name="repo_path")
def repo_fixture(tmp_path: Path) -> Path:
    """Create a temporary repository structure.

    The repository structure includes:
    - A ``.gitignore`` that excludes ``exclude.txt``
    - ``include.txt`` (should be processed)
    - ``exclude.txt`` (should be skipped when gitignore rules are respected)
    """
    # Create a .gitignore file that excludes 'exclude.txt'
    gitignore_file = tmp_path / ".gitignore"
    gitignore_file.write_text("exclude.txt\n")

    # Create a file that should be included
    include_file = tmp_path / "include.txt"
    include_file.write_text("This file should be included.")

    # Create a file that should be excluded
    exclude_file = tmp_path / "exclude.txt"
    exclude_file.write_text("This file should be excluded.")

    return tmp_path


def test_load_gitignore_patterns(tmp_path: Path) -> None:
    """Test that ``load_ignore_patterns()`` correctly loads patterns from a ``.gitignore`` file."""
    gitignore = tmp_path / ".gitignore"
    # Write some sample patterns with a comment line included
    gitignore.write_text("exclude.txt\n*.log\n# a comment\n")

    patterns = load_ignore_patterns(tmp_path, filename=".gitignore")

    # Check that the expected patterns are loaded
    assert "exclude.txt" in patterns
    assert "*.log" in patterns
    # Ensure that comment lines are not added
    for pattern in patterns:
        assert not pattern.startswith("#")


def test_load_gitignore_patterns_preserves_negation_order(tmp_path: Path) -> None:
    """Test that negated gitignore patterns keep their file order."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.log\n!important.log\n")

    assert load_ignore_patterns(tmp_path, filename=".gitignore") == ["*.log", "!important.log"]


@pytest.mark.asyncio
async def test_ingest_with_gitignore(repo_path: Path) -> None:
    """Integration test for ``ingest_async()`` respecting ``.gitignore`` rules.

    When ``include_gitignored`` is ``False`` (default), the content of ``exclude.txt`` should be omitted.
    When ``include_gitignored`` is ``True``, both files should be present.
    """
    # Run ingestion with the gitignore functionality enabled.
    _, _, content_with_ignore = await ingest_async(source=str(repo_path))
    # 'exclude.txt' should be skipped.
    assert "This file should be excluded." not in content_with_ignore
    # 'include.txt' should be processed.
    assert "This file should be included." in content_with_ignore

    # Run ingestion with the gitignore functionality disabled.
    _, _, content_without_ignore = await ingest_async(source=str(repo_path), include_gitignored=True)
    # Now both files should be present.
    assert "This file should be excluded." in content_without_ignore
    assert "This file should be included." in content_without_ignore


@pytest.mark.asyncio
async def test_ingest_with_gitignore_negation(tmp_path: Path) -> None:
    """Test that later negated gitignore rules can re-include files."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.log\n!important.log\n")

    ignored_file = tmp_path / "ignored.log"
    ignored_file.write_text("This log should be ignored.")

    important_file = tmp_path / "important.log"
    important_file.write_text("This log should be included.")

    _, _, content = await ingest_async(source=str(tmp_path))

    assert "This log should be ignored." not in content
    assert "This log should be included." in content
