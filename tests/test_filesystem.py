"""Tests for filesystem node content handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gitingest.schemas import FileSystemNode, FileSystemNodeType

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_content_keeps_utf8_text_when_multibyte_character_crosses_chunk_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preserve UTF-8 text when a chunk ends inside a multibyte character."""
    file_path = tmp_path / "boundary.py"
    content = f"{'a' * 1023}漢\n"
    file_path.write_text(content, encoding="utf-8")
    monkeypatch.setattr("gitingest.schemas.filesystem._get_preferred_encodings", lambda: ["utf-8"])

    node = FileSystemNode(
        name=file_path.name,
        type=FileSystemNodeType.FILE,
        path_str=file_path.name,
        path=file_path,
        size=file_path.stat().st_size,
    )

    assert node.content == content
