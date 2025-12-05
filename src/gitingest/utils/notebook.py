"""Utilities for processing Jupyter notebooks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import jupytext
from jupytext.config import JupytextConfiguration

from gitingest.utils.exceptions import InvalidNotebookError
from gitingest.utils.logging_config import get_logger

if TYPE_CHECKING:
    from pathlib import Path

# Initialize logger for this module
logger = get_logger(__name__)


def process_notebook(file: Path, *, include_output: bool = True) -> str:
    """Process a Jupyter notebook file and return an executable Python script as a string.

    Parameters
    ----------
    file : Path
        The path to the Jupyter notebook file.
    include_output : bool
        Whether to include cell outputs in the generated script (Not supported by Jupytext).
        This parameter is kept for backward compatibility but is ignored.

    Returns
    -------
    str
        The executable Python script as a string.

    Raises
    ------
    InvalidNotebookError
        If the notebook file is invalid or cannot be processed.

    """
    if include_output:
        # Jupytext does not support including outputs in the generated script
        # We log a debug message to inform the user
        logger.debug(
            "Jupytext does not support including outputs in the generated script. 'include_output' is ignored."
        )

    try:
        # Read the notebook using jupytext
        notebook = jupytext.read(file)

        # Convert to Python script
        # using "py:percent" format to preserve cell structure
        config = JupytextConfiguration()
        # We can add more config here if needed

        return jupytext.writes(notebook, fmt="py:percent")

    except Exception as exc:
        msg = f"Error processing notebook {file}: {exc}"
        raise InvalidNotebookError(msg) from exc
