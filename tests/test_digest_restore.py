"""Tests for digest parsing and project restoration."""

from __future__ import annotations

from pathlib import Path

import pytest

from gitingest.digest import parse_digest, restore_digest
from gitingest.schemas.filesystem import SEPARATOR


def test_parse_digest_extracts_file_and_symlink_entries() -> None:
    """It should parse FILE and SYMLINK blocks from digest text."""
    digest_text = (
        f"Directory structure:\n"
        f"└── sample/\n\n"
        f"{SEPARATOR}\n"
        "FILE: src/main.py\n"
        f"{SEPARATOR}\n"
        "print('hello')\n\n\n"
        f"{SEPARATOR}\n"
        "SYMLINK: src/latest.py -> main.py\n"
        f"{SEPARATOR}\n"
        "\n\n"
    )

    entries = parse_digest(digest_text)

    assert len(entries) == 2
    assert entries[0].entry_type == "FILE"
    assert entries[0].relative_path == "src/main.py"
    assert entries[0].content == "print('hello')"
    assert entries[1].entry_type == "SYMLINK"
    assert entries[1].relative_path == "src/latest.py"
    assert entries[1].symlink_target == "main.py"


def test_restore_digest_creates_project_files(tmp_path: Path) -> None:
    """It should recreate files and symlinks from a digest file."""
    digest_path = tmp_path / "digest.txt"
    digest_path.write_text(
        (
            f"{SEPARATOR}\n"
            "FILE: app.py\n"
            f"{SEPARATOR}\n"
            "print('ok')\n\n\n"
            f"{SEPARATOR}\n"
            "FILE: nested/config.txt\n"
            f"{SEPARATOR}\n"
            "ENV=dev\n\n\n"
            f"{SEPARATOR}\n"
            "SYMLINK: nested/latest.txt -> config.txt\n"
            f"{SEPARATOR}\n"
            "\n\n"
        ),
        encoding="utf-8",
    )

    files, symlinks, directories = restore_digest(digest_path=digest_path, destination=tmp_path / "restored")

    assert files == 2
    assert symlinks == 1
    assert directories == 1
    assert (tmp_path / "restored" / "app.py").read_text(encoding="utf-8") == "print('ok')"
    assert (tmp_path / "restored" / "nested" / "config.txt").read_text(encoding="utf-8") == "ENV=dev"
    assert (tmp_path / "restored" / "nested" / "latest.txt").is_symlink()


def test_restore_digest_rejects_path_traversal(tmp_path: Path) -> None:
    """It should reject digest entries that escape the destination path."""
    digest_path = tmp_path / "digest.txt"
    digest_path.write_text(
        (
            f"{SEPARATOR}\n"
            "FILE: ../escape.txt\n"
            f"{SEPARATOR}\n"
            "escaped\n\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="outside destination directory"):
        restore_digest(digest_path=digest_path, destination=tmp_path / "restored")
