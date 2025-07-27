"""Schema for the filesystem representation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING
from abc import ABC
from functools import singledispatchmethod

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

@dataclass
class Source(ABC):
    """Abstract base class for all sources (files, directories, etc)."""
    @property
    def tree(self) -> str:
        return self._tree()
    @property
    def summary(self) -> str:
        return getattr(self, "_summary", "")
    @summary.setter
    def summary(self, value: str) -> None:
        self._summary = value

@dataclass
class FileSystemNode(Source):
    name: str
    path_str: str
    path: Path
    depth: int = 0
    size: int = 0

    @property
    def tree(self):
        return self._tree()

    @singledispatchmethod
    def _tree(self):
        return self.name

@dataclass
class FileSystemFile(FileSystemNode):
    @property
    def content(self):
        # read the file
        try:
            with open(self.path, "r") as f:
                return f.read()
        except Exception as e:
            return f"Error reading content of {self.name}: {e}"

@dataclass
class FileSystemTextFile(FileSystemFile):
    pass

@FileSystemNode._tree.register
def _(self: 'FileSystemFile'):
    return self.name

@dataclass
class FileSystemDirectory(FileSystemNode):
    children: list['FileSystemNode'] = field(default_factory=list)
    file_count: int = 0
    dir_count: int = 0
    type: FileSystemNodeType = FileSystemNodeType.DIRECTORY

    def sort_children(self) -> None:
        """Sort the children nodes of a directory according to a specific order."""
        def _sort_key(child: FileSystemNode) -> tuple[int, str]:
            name = child.name.lower()
            if hasattr(child, 'type') and getattr(child, 'type', None) == FileSystemNodeType.FILE:
                if name == "readme" or name.startswith("readme."):
                    return (0, name)
                return (1 if not name.startswith(".") else 2, name)
            return (3 if not name.startswith(".") else 4, name)
        self.children.sort(key=_sort_key)

@FileSystemNode._tree.register
def _(self: 'FileSystemDirectory'):
    def render_tree(node, prefix="", is_last=True):
        lines = []
        current_prefix = "└── " if is_last else "├── "
        display_name = node.name + "/"
        lines.append(f"{prefix}{current_prefix}{display_name}")
        if hasattr(node, 'children') and node.children:
            new_prefix = prefix + ("    " if is_last else "│   ")
            for i, child in enumerate(node.children):
                is_last_child = i == len(node.children) - 1
                lines.extend(child._tree()(child, prefix=new_prefix, is_last=is_last_child) if hasattr(child, '_tree') else [child.name])
        return lines
    return "\n".join(render_tree(self))

@dataclass
class FileSystemSymlink(FileSystemNode):
    target: str = ""
    # Add symlink-specific fields if needed

@FileSystemNode._tree.register
def _(self: 'FileSystemSymlink'):
    return f"{self.name} -> {self.target}" if self.target else self.name


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