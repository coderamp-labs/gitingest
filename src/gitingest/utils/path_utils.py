"""Utility functions for working with file paths."""

import platform
from pathlib import Path


def _is_safe_symlink(symlink_path: Path, base_path: Path) -> bool:
    """Return ``True`` if ``symlink_path`` resolves inside ``base_path``.

    Parameters
    ----------
    symlink_path : Path
        Symlink whose target should be validated.
    base_path : Path
        Directory that the symlink target must remain within.

    Returns
    -------
    bool
        Whether the symlink is "safe" (i.e., does not escape ``base_path``).

    """
    # On Windows a non-symlink is immediately unsafe
    if platform.system() == "Windows" and not symlink_path.is_symlink():
        return False

    try:
        target_path = symlink_path.resolve()
        base_resolved = base_path.resolve()
    except (OSError, ValueError):
        # Any resolution error → treat as unsafe
        return False

    return base_resolved in target_path.parents or target_path == base_resolved
