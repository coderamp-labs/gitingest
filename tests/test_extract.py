"""Unit tests for the gitingest.extract module."""

from __future__ import annotations

import os
import pytest
from pathlib import Path

from gitingest.extract import extract
from gitingest.schemas.filesystem import SEPARATOR


def test_extract_basic_file(tmp_path: Path) -> None:
    """Test basic extraction of a single text file."""
    digest_content = (
        "Directory structure:\n"
        "└── file1.txt\n\n"
        f"{SEPARATOR}\n"
        "FILE: file1.txt\n"
        f"{SEPARATOR}\n"
        "Hello, World!\n\n\n"
    )
    digest_file = tmp_path / "test_digest.txt"
    digest_file.write_text(digest_content, encoding="utf-8")

    output_dir = tmp_path / "extracted_output"
    extract(digest_file, output_dir)

    extracted_file = output_dir / "file1.txt"
    assert extracted_file.exists()
    assert extracted_file.read_text(encoding="utf-8") == "Hello, World!"


def test_extract_to_specified_directory(tmp_path: Path) -> None:
    """Test extraction to a custom output directory."""
    digest_content = (
        "Directory structure:\n"
        "└── sub/file.txt\n\n"
        f"{SEPARATOR}\n"
        "FILE: sub/file.txt\n"
        f"{SEPARATOR}\n"
        "Content in subfolder.\n\n\n"
    )
    digest_file = tmp_path / "custom_digest.txt"
    digest_file.write_text(digest_content, encoding="utf-8")

    output_dir = tmp_path / "my_custom_output"
    extract(digest_file, output_dir)

    extracted_file = output_dir / "sub" / "file.txt"
    assert extracted_file.exists()
    assert extracted_file.read_text(encoding="utf-8") == "Content in subfolder."


def test_extract_empty_file(tmp_path: Path) -> None:
    """Test extraction of an empty file placeholder."""
    digest_content = (
        "Directory structure:\n"
        "└── empty.txt\n\n"
        f"{SEPARATOR}\n"
        "FILE: empty.txt\n"
        f"{SEPARATOR}\n"
        "[Empty file]\n\n\n"
    )
    digest_file = tmp_path / "empty_digest.txt"
    digest_file.write_text(digest_content, encoding="utf-8")

    output_dir = tmp_path / "output_empty"
    extract(digest_file, output_dir)

    extracted_file = output_dir / "empty.txt"
    assert extracted_file.exists()
    assert extracted_file.read_text(encoding="utf-8") == "[Empty file]"


def test_extract_binary_file_placeholder(tmp_path: Path) -> None:
    """Test extraction of a binary file placeholder."""
    digest_content = (
        "Directory structure:\n"
        "└── image.png\n\n"
        f"{SEPARATOR}\n"
        "FILE: image.png\n"
        f"{SEPARATOR}\n"
        "[Binary file]\n\n\n"
    )
    digest_file = tmp_path / "binary_digest.txt"
    digest_file.write_text(digest_content, encoding="utf-8")

    output_dir = tmp_path / "output_binary"
    extract(digest_file, output_dir)

    extracted_file = output_dir / "image.png"
    assert extracted_file.exists()
    assert extracted_file.read_text(encoding="utf-8") == "[Binary file]"


def test_extract_symlink(tmp_path: Path) -> None:
    """Test extraction of a symlink."""
    # Create a target file first
    target_file = tmp_path / "target.txt"
    target_file.write_text("This is the target.", encoding="utf-8")

    digest_content = (
        "Directory structure:\n"
        "├── target.txt\n"
        "└── link.txt -> target.txt\n\n"
        f"{SEPARATOR}\n"
        "FILE: target.txt\n"
        f"{SEPARATOR}\n"
        "This is the target.\n\n\n"
        f"{SEPARATOR}\n"
        "SYMLINK: link.txt -> target.txt\n"
        f"{SEPARATOR}\n"
        "\n\n"  # Symlinks have empty content in the digest
    )
    digest_file = tmp_path / "symlink_digest.txt"
    digest_file.write_text(digest_content, encoding="utf-8")

    output_dir = tmp_path / "output_symlink"
    extract(digest_file, output_dir)

    extracted_symlink = output_dir / "link.txt"
    extracted_target = output_dir / "target.txt"

    assert extracted_target.exists()
    assert extracted_target.read_text() == "This is the target."
    assert extracted_symlink.is_symlink()
    assert os.readlink(extracted_symlink) == str(Path("target.txt"))  # Symlink target is relative


def test_extract_file_not_found(tmp_path: Path) -> None:
    """Test that FileNotFoundError is raised for a missing digest file."""
    non_existent_digest = tmp_path / "non_existent.txt"
    output_dir = tmp_path / "output_error"

    with pytest.raises(FileNotFoundError, match="Digest file not found"):
        extract(non_existent_digest, output_dir)
