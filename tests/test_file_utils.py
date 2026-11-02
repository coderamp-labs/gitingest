"""Tests for file reading, encoding detection, and binary heuristics."""

from __future__ import annotations

from pathlib import Path

from gitingest.schemas.filesystem import FileSystemNode, FileSystemNodeType
from gitingest.utils.file_utils import _decodes


def test_decodes_handles_chunk_boundary_truncated_multibyte() -> None:
    """Test that _decodes returns True when a multi-byte sequence is split at chunk boundary."""
    # 3-byte Chinese characters in UTF-8
    chinese_text = "你好世界" * 100
    encoded = chinese_text.encode("utf-8")
    # Take 1024 bytes, which splits a 3-byte character
    chunk = encoded[:1024]

    assert _decodes(chunk, "utf-8") is True


def test_decodes_rejects_corrupted_bytes() -> None:
    """Test that _decodes returns False for genuinely invalid byte sequences."""
    corrupted_chunk = b"Valid text but then invalid \xff\xfe random"
    assert _decodes(corrupted_chunk, "utf-8") is False


def test_multibyte_markdown_file_not_misrecognized_as_binary(tmp_path: Path) -> None:
    """Test that a Markdown file with multi-byte characters is read as text, not [Binary file] (issue #613)."""
    # Create markdown file where byte 1024 splits a UTF-8 character
    content = "# Life Experience\n\n" + ("这是一篇很长的中文经历记录，包含许多段落和字符。\n" * 50)
    file_path = tmp_path / "life_experience.md"
    file_path.write_text(content, encoding="utf-8")

    node = FileSystemNode(
        name="life_experience.md",
        type=FileSystemNodeType.FILE,
        path_str="life_experience.md",
        path=file_path,
        size=len(content.encode("utf-8")),
    )

    result = node.content
    assert result != "[Binary file]"
    assert "# Life Experience" in result
    assert "经历记录" in result


def test_binary_file_with_null_bytes_recognized_as_binary(tmp_path: Path) -> None:
    """Test that a binary file with null bytes is recognized as [Binary file]."""
    file_path = tmp_path / "image.png"
    file_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00")

    node = FileSystemNode(
        name="image.png",
        type=FileSystemNodeType.FILE,
        path_str="image.png",
        path=file_path,
        size=file_path.stat().st_size,
    )

    assert node.content == "[Binary file]"


def test_utf16_file_with_bom_read_as_text(tmp_path: Path) -> None:
    """Test that a UTF-16 file with BOM is decoded and read properly."""
    content = "Hello from UTF-16 file\n"
    file_path = tmp_path / "utf16.txt"
    file_path.write_text(content, encoding="utf-16")

    node = FileSystemNode(
        name="utf16.txt",
        type=FileSystemNodeType.FILE,
        path_str="utf16.txt",
        path=file_path,
        size=file_path.stat().st_size,
    )

    assert node.content == content


def test_empty_file_recognized_as_empty(tmp_path: Path) -> None:
    """Test that an empty file returns [Empty file]."""
    file_path = tmp_path / "empty.txt"
    file_path.write_bytes(b"")

    node = FileSystemNode(
        name="empty.txt",
        type=FileSystemNodeType.FILE,
        path_str="empty.txt",
        path=file_path,
        size=0,
    )

    assert node.content == "[Empty file]"
