"""Schema for the filesystem representation."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from gitingest.schemas import IngestionQuery

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
class Source(ABC):
    """Abstract base class for all sources (files, directories, etc)."""


@dataclass
class FileSystemNode(Source):
    name: str
    path_str: str
    path: Path
    depth: int = 0
    size: int = 0

    @property
    def tree(self):
        return self.name


@dataclass
class FileSystemFile(FileSystemNode):
    @property
    def content(self):
        # read the file
        try:
            with open(self.path) as f:
                return f.read()
        except Exception as e:
            return f"Error reading content of {self.name}: {e}"

    def render_tree(self, prefix="", is_last=True):
        current_prefix = "└── " if is_last else "├── "
        return [f"{prefix}{current_prefix}{self.name}"]


@dataclass
class FileSystemDirectory(FileSystemNode):
    children: list[FileSystemNode] = field(default_factory=list)
    file_count: int = 0
    dir_count: int = 0
    type: FileSystemNodeType = FileSystemNodeType.DIRECTORY

    def sort_children(self) -> None:
        """Sort the children nodes of a directory according to a specific order."""

        def _sort_key(child: FileSystemNode) -> tuple[int, str]:
            name = child.name.lower()
            if hasattr(child, "type") and getattr(child, "type", None) == FileSystemNodeType.FILE:
                if name == "readme" or name.startswith("readme."):
                    return (0, name)
                return (1 if not name.startswith(".") else 2, name)
            return (3 if not name.startswith(".") else 4, name)

        self.children.sort(key=_sort_key)

    def render_tree(self, prefix="", is_last=True):
        lines = []
        current_prefix = "└── " if is_last else "├── "
        display_name = self.name + "/"
        lines.append(f"{prefix}{current_prefix}{display_name}")
        if hasattr(self, "children") and self.children:
            new_prefix = prefix + ("    " if is_last else "│   ")
            for i, child in enumerate(self.children):
                is_last_child = i == len(self.children) - 1
                lines.extend(child.render_tree(prefix=new_prefix, is_last=is_last_child))
        return lines

    @property
    def tree(self):
        return "\n".join(self.render_tree())


@dataclass
class GitRepository(FileSystemDirectory):
    """A directory that contains a .git folder, representing a Git repository."""

    git_info: dict = field(default_factory=dict)  # Store git metadata like branch, commit, etc.

    def render_tree(self, prefix="", is_last=True):
        lines = []
        current_prefix = "└── " if is_last else "├── "
        # Mark as git repo in the tree
        display_name = f"{self.name}/ (git repository)"
        lines.append(f"{prefix}{current_prefix}{display_name}")
        if hasattr(self, "children") and self.children:
            new_prefix = prefix + ("    " if is_last else "│   ")
            for i, child in enumerate(self.children):
                is_last_child = i == len(self.children) - 1
                lines.extend(child.render_tree(prefix=new_prefix, is_last=is_last_child))
        return lines


@dataclass
class FileSystemSymlink(FileSystemNode):
    target: str = ""
    # Add symlink-specific fields if needed

    def render_tree(self, prefix="", is_last=True):
        current_prefix = "└── " if is_last else "├── "
        display_name = f"{self.name} -> {self.target}" if self.target else self.name
        return [f"{prefix}{current_prefix}{display_name}"]


class Context(Source):
    """The Context object is a general container for multiple unrelated sources.

    Attributes
    ----------
    sources : list[Source]
        The list of source objects to format.
    query : IngestionQuery
        The query context.

    """

    def __init__(self, sources: list[Source], query: IngestionQuery):
        self.sources = sources
        self.query = query
