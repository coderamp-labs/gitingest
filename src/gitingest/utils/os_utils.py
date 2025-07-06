"""Utility functions for working with the operating system."""

from pathlib import Path


async def ensure_directory_exists_or_create(path: Path) -> None:
    """Ensure the directory exists, creating it if necessary.

    Parameters
    ----------
    path : Path
        The path to ensure exists.

    Raises
    ------
    OSError
        If the directory cannot be created.

    """
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        msg = f"Failed to create directory {path}: {exc}"
        raise OSError(msg) from exc
