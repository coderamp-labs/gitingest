"""Schema for the filesystem representation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from gitingest.utils.compat_func import readlink
from gitingest.utils.file_utils import _decodes, _get_preferred_encodings, _read_chunk
from gitingest.utils.notebook import process_notebook

if TYPE_CHECKING:
    from pathlib import Path

SEPARATOR = "=" * 48  # Tiktoken, the tokenizer openai uses, counts 2 tokens if we have more than 48


class FileSystemNodeType(Enum):
    """Enum representing the type of a file system node (directory or file)."""

    DIRECTORY = auto()
    FILE = auto()
    SYMLINK = auto()


@dataclass
class FileSystemStats:
    """Class for tracking statistics during file system traversal."""

    total_files: int = 0
    total_size: int = 0


@dataclass
class FileSystemNode:  # pylint: disable=too-many-instance-attributes
    """Class representing a node in the file system (either a file or directory).

    Tracks properties of files/directories for comprehensive analysis.
    """

    name: str
    type: FileSystemNodeType
    path_str: str
    path: Path
    size: int = 0
    file_count: int = 0
    dir_count: int = 0
    depth: int = 0
    children: list[FileSystemNode] = field(default_factory=list)

    def sort_children(self) -> None:
        """Sort the children nodes of a directory according to a specific order.

        Order of sorting:
          2. Regular files (not starting with dot)
          3. Hidden files (starting with dot)
          4. Regular directories (not starting with dot)
          5. Hidden directories (starting with dot)

        All groups are sorted alphanumerically within themselves.

        Raises
        ------
        ValueError
            If the node is not a directory.

        """
        if self.type != FileSystemNodeType.DIRECTORY:
            msg = "Cannot sort children of a non-directory node"
            raise ValueError(msg)

        def _sort_key(child: FileSystemNode) -> tuple[int, str]:
            # returns the priority order for the sort function, 0 is first
            # Groups: 0=README, 1=regular file, 2=hidden file, 3=regular dir, 4=hidden dir
            name = child.name.lower()
            if child.type == FileSystemNodeType.FILE:
                if name == "readme" or name.startswith("readme."):
                    return (0, name)
                return (1 if not name.startswith(".") else 2, name)
            return (3 if not name.startswith(".") else 4, name)

        self.children.sort(key=_sort_key)

    @property
    def content_string(self) -> str:
        """Return the content of the node as a string, including path and content.

        Returns
        -------
        str
            A string representation of the node's content.

        """
        parts = [
            SEPARATOR,
            f"{self.type.name}: {str(self.path_str).replace(os.sep, '/')}"
            + (f" -> {readlink(self.path).name}" if self.type == FileSystemNodeType.SYMLINK else ""),
            SEPARATOR,
            f"{self.content}",
        ]

        return "\n".join(parts) + "\n\n"

    @property
    def content(self) -> str:  # pylint: disable=too-many-return-statements
        """Return file content (if text / notebook) or an explanatory placeholder.

        Heuristically decides whether the file is text or binary by decoding a small chunk of the file
        with multiple encodings and checking for common binary markers.

        Returns
        -------
        str
            The content of the file, or an error message if the file could not be read.

        Raises
        ------
        ValueError
            If the node is a directory.

        """
        if self.type == FileSystemNodeType.DIRECTORY:
            msg = "Cannot read content of a directory node"
            raise ValueError(msg)

        if self.type == FileSystemNodeType.SYMLINK:
            return ""  # TODO: are we including the empty content of symlinks?

        if self.path.suffix == ".ipynb":  # Notebook
            try:
                return process_notebook(self.path)
            except Exception as exc:
                return f"Error processing notebook: {exc}"

        chunk = _read_chunk(self.path)

        if chunk is None:
            return "Error reading file"

        if chunk == b"":
            return "[Empty file]"

        if not _decodes(chunk, "utf-8"):
            return "[Binary file]"

        # Find the first encoding that decodes the sample
        good_enc: str | None = next(
            (enc for enc in _get_preferred_encodings() if _decodes(chunk, encoding=enc)),
            None,
        )

        if good_enc is None:
            return "Error: Unable to decode file with available encodings"

        try:
            with self.path.open(encoding=good_enc) as fp:
                return fp.read()
        except (OSError, UnicodeDecodeError) as exc:
            return f"Error reading file with {good_enc!r}: {exc}"
