"""Utilities for restoring a project from a gitingest digest file."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from gitingest.schemas.filesystem import SEPARATOR

_BLOCK_HEADER_RE = re.compile(r"^(FILE|SYMLINK): (.+?)(?: -> (.+))?$")


@dataclass
class DigestEntry:
    """A single digest block for a file or symlink."""

    entry_type: str
    relative_path: str
    content: str
    symlink_target: str | None = None


def parse_digest(text: str) -> list[DigestEntry]:
    """Parse digest text and return all file/symlink entries in order."""
    entries: list[DigestEntry] = []
    position = 0

    while True:
        block = _find_block(text, position)
        if block is None:
            break

        start, content_start, entry_type, relative_path, symlink_target = block
        next_start = _find_next_block_start(text, content_start)
        if next_start is None:
            raw_content = text[content_start:]
            position = len(text)
            content = _trim_synthetic_suffix(raw_content, inter_block=False)
        else:
            raw_content = text[content_start:next_start]
            position = next_start
            content = _trim_synthetic_suffix(raw_content, inter_block=True)

        entries.append(
            DigestEntry(
                entry_type=entry_type,
                relative_path=relative_path,
                content=content,
                symlink_target=symlink_target,
            ),
        )

    return entries


def restore_digest(
    digest_path: str | Path,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> tuple[int, int, int]:
    """Restore files from ``digest_path`` into ``destination``.

    Returns ``(restored_files, restored_symlinks, directories)``.
    """
    digest_file = Path(digest_path)
    destination_dir = Path(destination)
    destination_dir.mkdir(parents=True, exist_ok=True)

    entries = parse_digest(digest_file.read_text(encoding="utf-8"))
    if not entries:
        msg = "No FILE or SYMLINK entries were found in the digest."
        raise ValueError(msg)

    restored_files = 0
    restored_symlinks = 0
    restored_directories: set[Path] = set()
    for entry in entries:
        output_path = _safe_join(destination_dir, entry.relative_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.parent != destination_dir:
            restored_directories.add(output_path.parent)

        if entry.entry_type == "FILE":
            _write_file(output_path, entry.content, overwrite=overwrite)
            restored_files += 1
        elif entry.entry_type == "SYMLINK":
            _write_symlink(output_path, entry.symlink_target, overwrite=overwrite)
            restored_symlinks += 1

    return restored_files, restored_symlinks, len(restored_directories)


def _find_block(text: str, start: int) -> tuple[int, int, str, str, str | None] | None:
    marker = f"{SEPARATOR}\n"
    idx = text.find(marker, start)
    while idx != -1:
        header_start = idx + len(marker)
        header_end = text.find("\n", header_start)
        if header_end == -1:
            return None

        second_sep_start = header_end + 1
        second_marker = f"{SEPARATOR}\n"
        if not text.startswith(second_marker, second_sep_start):
            idx = text.find(marker, header_start)
            continue

        header = text[header_start:header_end]
        match = _BLOCK_HEADER_RE.match(header)
        if match is None:
            idx = text.find(marker, header_start)
            continue

        content_start = second_sep_start + len(second_marker)
        return idx, content_start, match.group(1), match.group(2), match.group(3)

    return None


def _find_next_block_start(text: str, start: int) -> int | None:
    marker = f"\n{SEPARATOR}\n"
    idx = text.find(marker, start)
    while idx != -1:
        candidate = _find_block(text, idx + 1)
        if candidate and candidate[0] == idx + 1:
            return idx
        idx = text.find(marker, idx + 1)
    return None


def _trim_synthetic_suffix(content: str, *, inter_block: bool) -> str:
    if inter_block and content.endswith("\n\n\n"):
        return content[:-3]
    if content.endswith("\n\n"):
        return content[:-2]
    return content


def _safe_join(base_dir: Path, relative_path: str) -> Path:
    output_path = (base_dir / relative_path).resolve()
    base_resolved = base_dir.resolve()
    if output_path != base_resolved and base_resolved not in output_path.parents:
        msg = f"Refusing to write outside destination directory: {relative_path}"
        raise ValueError(msg)
    return output_path


def _write_file(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        msg = f"Refusing to overwrite existing path: {path}"
        raise FileExistsError(msg)
    path.write_text(content, encoding="utf-8")


def _write_symlink(path: Path, target: str | None, *, overwrite: bool) -> None:
    if not target:
        msg = f"Invalid symlink entry for path: {path}"
        raise ValueError(msg)

    if path.exists() or path.is_symlink():
        if not overwrite:
            msg = f"Refusing to overwrite existing path: {path}"
            raise FileExistsError(msg)
        path.unlink()
    path.symlink_to(target)
