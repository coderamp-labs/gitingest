"""Regression tests for the text/binary detection in ``FileSystemNode.content``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from gitingest.schemas.filesystem import FileSystemNode, FileSystemNodeType
from gitingest.utils.file_utils import _decodes

if TYPE_CHECKING:
    from pathlib import Path


def _node(path: Path) -> FileSystemNode:
    return FileSystemNode(name=path.name, type=FileSystemNodeType.FILE, path_str=str(path), path=path)


def test_utf8_text_cut_mid_character_by_the_sample_is_text(tmp_path: Path) -> None:
    """A UTF-8 file whose 1024-byte sample ends inside a character is still text.

    Every Chinese character is three bytes, so the 1024-byte sample boundary lands in the
    middle of one of them and a strict decode of the sample fails.
    """
    path = tmp_path / "experiences.md"
    text = "个人经历 " * 120
    path.write_text(text, encoding="utf-8")

    assert _node(path).content == text


def test_utf8_text_with_non_ascii_markup_is_not_binary(tmp_path: Path) -> None:
    """A UTF-8 file with accented characters is decoded as UTF-8, not the platform default."""
    path = tmp_path / "notes.md"
    text = "# Résumé\n\n" + "élève " * 300
    path.write_text(text, encoding="utf-8")

    assert _node(path).content == text


def test_binary_file_is_still_reported_as_binary(tmp_path: Path) -> None:
    """Bytes that are not valid UTF-8 are still reported as a binary file."""
    path = tmp_path / "blob.bin"
    path.write_bytes(b"\x00\x01\x02\xff\xfe" * 300)

    assert _node(path).content == "[Binary file]"


@pytest.mark.parametrize(
    ("chunk", "expected"),
    [
        ("汉".encode()[:2], True),  # only the trailing character is incomplete
        (b"hello \xff\xfe", False),  # invalid bytes before the end
        (b"\x00\x01\x02", True),  # NUL bytes decode as text; the sample decoding is not the guard
    ],
)
def test_decodes_ignores_only_an_incomplete_trailing_character(chunk: bytes, *, expected: bool) -> None:
    """A cut multi-byte character is tolerated, invalid bytes in the middle are not."""
    assert _decodes(chunk, "utf-8") is expected
