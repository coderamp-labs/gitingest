"""Tests for Windows encoding handling."""

from pathlib import Path
from unittest.mock import patch

from gitingest.schemas.filesystem import FileSystemNode, FileSystemNodeType
from gitingest.utils.file_utils import _CHUNK_SIZE


def test_utf8_priority_on_windows(tmp_path: Path) -> None:
    """Ensure UTF-8 files are read correctly even on Windows systems defaulting to cp1252.

    This test reproduces a specific crash scenario where:
    1. A file is valid UTF-8.
    2. The first 1024 bytes are safe ASCII (passing the initial CP1252 check).
    3. Subsequent bytes contain characters undefined in CP1252 (e.g., smart quotes),
       causing a UnicodeDecodeError if CP1252 is preferred over UTF-8.
    """
    file_path = tmp_path / "test_encoding_crash.md"

    # The right double quotation mark (”) is:
    # - UTF-8: 0xE2 0x80 0x9D
    # - CP1252: Byte 0x9D is UNDEFINED and causes a crash during full read.
    poison_char = "”"

    # Fill buffer to bypass the initial chunk read (which checks the first 1024 bytes)
    content = ("a" * (_CHUNK_SIZE + 50)) + poison_char + "\nEnd."

    file_path.write_text(content, encoding="utf-8")

    node = FileSystemNode(
        name=file_path.name,
        type=FileSystemNodeType.FILE,
        path_str=str(file_path),
        path=file_path,
        size=file_path.stat().st_size,
    )

    # Mock the environment to simulate Windows with CP1252 locale
    with patch("locale.getpreferredencoding", return_value="cp1252"), patch(
        "platform.system",
        return_value="Windows",
    ):
        read_content = node.content

        assert "Error reading file" not in read_content, "Failed to read valid UTF-8 file on Windows/CP1252 simulation"
        assert poison_char in read_content, "Failed to correctly decode the special character"
        assert read_content.endswith("End."), "Content appears truncated or malformed"
