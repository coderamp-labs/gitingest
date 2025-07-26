"""Utility functions for the ingestion process."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pathspec import PathSpec

if TYPE_CHECKING:
    from pathlib import Path


def _should_include(path: Path, base_path: Path, include_patterns: set[str]) -> bool:
    """Return ``True`` if ``path`` matches any of ``include_patterns``.

    Parameters
    ----------
    path : Path
        The absolute path of the file or directory to check.

    base_path : Path
        The base directory from which the relative path is calculated.

    include_patterns : set[str]
        A set of patterns to check against the relative path.

    Returns
    -------
    bool
        ``True`` if the path matches any of the include patterns, ``False`` otherwise.

    """
    rel_path = _relative_or_none(path, base_path)
    if rel_path is None:  # outside repo → do *not* include
        return False
    if path.is_dir():  # keep directories so children are visited
        return True

    spec = PathSpec.from_lines("gitwildmatch", include_patterns)
    return spec.match_file(str(rel_path))


def _should_exclude(path: Path, base_path: Path, ignore_patterns: set[str]) -> bool:
    """Return ``True`` if ``path`` matches any of ``ignore_patterns``.

    Parameters
    ----------
    path : Path
        The absolute path of the file or directory to check.
    base_path : Path
        The base directory from which the relative path is calculated.
    ignore_patterns : set[str]
        A set of patterns to check against the relative path.

    Returns
    -------
    bool
        ``True`` if the path matches any of the ignore patterns, ``False`` otherwise.

    """
    rel_path = _relative_or_none(path, base_path)
    if rel_path is None:  # outside repo → already "excluded"
        return True

    spec = PathSpec.from_lines("gitwildmatch", ignore_patterns)
    return spec.match_file(str(rel_path))


def _relative_or_none(path: Path, base: Path) -> Path | None:
    """Return *path* relative to *base* or ``None`` if *path* is outside *base*.

    Parameters
    ----------
    path : Path
        The absolute path of the file or directory to check.
    base : Path
        The base directory from which the relative path is calculated.

    Returns
    -------
    Path | None
        The relative path of ``path`` to ``base``, or ``None`` if ``path`` is outside ``base``.

    """
    try:
        return path.relative_to(base)
    except ValueError:  # path is not a sub-path of base
        return None
