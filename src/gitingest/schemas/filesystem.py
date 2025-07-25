"""Schema for the filesystem representation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING
from abc import ABC

from gitingest.utils.compat_func import readlink
from gitingest.utils.file_utils import _decodes, _get_preferred_encodings, _read_chunk
from gitingest.utils.notebook import process_notebook

if TYPE_CHECKING:
    from pathlib import Path
    from gitingest.schemas import IngestionQuery
    from gitingest.output_formatter import Formatter

SEPARATOR = "=" * 48  # Tiktoken, the tokenizer openai uses, counts 2 tokens if we have more than 48
CONTEXT_HEADER = "# Generated using https://gitingest.com{}\n" # Replace with /user/repo if we have it otherwise leave it blank
CONTEXT_FOOTER = "# End of gitingest context\n"

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


class Source:
    """Abstract base class for all sources (files, directories, etc)."""
    summary: str = ""
    tree: str = ""
    @property
    def content(self) -> str:
        return self._content
    @content.setter
    def content(self, value: str) -> None:
        self._content = value

class FileSystemNode(Source):
    """Base class for all file system nodes (file, directory, symlink)."""
    def __init__(self, name: str, path_str: str, path: 'Path', depth: int = 0):
        self.name = name
        self.path_str = path_str
        self.path = path
        self.depth = depth
        self.summary = ""
        self.tree = ""
        self.children: list[FileSystemNode] = []
        self.size: int = 0

    @property
    def content(self) -> str:
        raise NotImplementedError("Content is not implemented for FileSystemNode")

class FileSystemFile(FileSystemNode):
    @property
    def content(self) -> str:
        with open(self.path, "r", encoding="utf-8") as f:
            return f.read()

class FileSystemDirectory(FileSystemNode):
    children: list['FileSystemNode'] = field(default_factory=list)
    file_count: int = 0
    dir_count: int = 0
    type: FileSystemNodeType = FileSystemNodeType.DIRECTORY

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
            if hasattr(child, 'type') and child.type == FileSystemNodeType.FILE:
                if name == "readme" or name.startswith("readme."):
                    return (0, name)
                return (1 if not name.startswith(".") else 2, name)
            return (3 if not name.startswith(".") else 4, name)

        self.children.sort(key=_sort_key)

class FileSystemSymlink(FileSystemNode):
    # Add symlink-specific fields if needed
    pass


@dataclass
class Context:
    """Context for holding a list of Source objects and generating a digest on demand using a Formatter.

    Attributes
    ----------
    nodes : list[Source]
        The list of source objects to generate a digest for.
    formatter : Formatter
        The formatter to use for formatting sources.
    query : IngestionQuery
        The query context.
    """
    nodes: list[Source]
    formatter: Formatter
    query: IngestionQuery

    def generate_digest(self) -> str:
        if self.query.user_name and self.query.repo_name:
            context_header = CONTEXT_HEADER.format(f"/{self.query.user_name}/{self.query.repo_name}")
        else:
            context_header = CONTEXT_HEADER.format("")
        context_footer = CONTEXT_FOOTER
        formatted = []
        for node in self.nodes:
            formatted.append(self.formatter.format(node, self.query))
        return context_header + "\n".join(formatted) + context_footer

    @property
    def summary(self):
        return "\n".join(self.formatter.summary(node, self.query) for node in self.nodes)