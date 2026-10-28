"""Utility functions for working with files and directories."""

from __future__ import annotations

import codecs
import locale
import platform
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    locale.setlocale(locale.LC_ALL, "C")

_CHUNK_SIZE = 1024  # bytes


def _get_preferred_encodings() -> list[str]:
    """Get list of encodings to try, prioritized for text files.

    Returns
    -------
    list[str]
        List of encoding names to try in priority order, starting with UTF-8 followed by the
        platform's default encoding and common fallback encodings.

    """
    encodings = ["utf-8", locale.getpreferredencoding(), "utf-16", "utf-16le", "utf-8-sig", "latin"]
    if platform.system() == "Windows":
        encodings += ["cp1252", "iso-8859-1"]
    return list(dict.fromkeys(encodings))


def _read_chunk(path: Path) -> bytes | None:
    """Attempt to read the first *size* bytes of *path* in binary mode.

    Parameters
    ----------
    path : Path
        The path to the file to read.

    Returns
    -------
    bytes | None
        The first ``_CHUNK_SIZE`` bytes of ``path``, or ``None`` on any ``OSError``.

    """
    try:
        with path.open("rb") as fp:
            return fp.read(_CHUNK_SIZE)
    except OSError:
        return None


def _decodes(chunk: bytes, encoding: str) -> bool:
    """Return ``True`` if ``chunk`` decodes cleanly with ``encoding``.

    The chunk is a prefix of the file, so its last character can be cut in half by the read
    boundary. Only the complete part is decoded here; an incomplete trailing sequence is not a
    decoding error, while invalid bytes anywhere else still are.

    Parameters
    ----------
    chunk : bytes
        The chunk of bytes to decode.
    encoding : str
        The encoding to use to decode the chunk.

    Returns
    -------
    bool
        ``True`` if the chunk decodes cleanly with the encoding, ``False`` otherwise.

    """
    try:
        codecs.getincrementaldecoder(encoding)().decode(chunk, final=False)
    except (UnicodeDecodeError, LookupError):
        return False
    return True
