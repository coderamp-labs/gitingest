"""Schema for the filesystem representation."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gitingest.schemas.source import Source

if TYPE_CHECKING:
    from pathlib import Path

SEPARATOR = "=" * 48  # Tiktoken, the tokenizer openai uses, counts 2 tokens if we have more than 48


@dataclass
class FileSystemStats:
    """Class for tracking statistics during file system traversal."""

    total_files: int = 0
    total_size: int = 0


@dataclass
class FileSystemNode(Source, ABC):  # pylint: disable=too-many-instance-attributes
    """Abstract base class for filesystem nodes (files, directories, symlinks)."""

    # Required fields - use None defaults and validate in __post_init__
    name: str | None = None
    path_str: str | None = None
    path: "Path | None" = None
    
    # Optional fields with sensible defaults
    size: int = 0
    file_count: int = 0
    dir_count: int = 0
    depth: int = 0
    children: list[FileSystemNode] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        if self.name is None:
            raise ValueError("FileSystemNode requires 'name' field")
        if self.path_str is None:
            raise ValueError("FileSystemNode requires 'path_str' field")
        if self.path is None:
            raise ValueError("FileSystemNode requires 'path' field")

    # Abstract methods - must be implemented by subclasses
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Display name for tree view (e.g., file.py, dir/, symlink -> target)."""
        
    @property
    @abstractmethod
    def node_type(self) -> str:
        """Type name for content string header (FILE, DIRECTORY, SYMLINK)."""
        
    @property
    @abstractmethod
    def is_single_file(self) -> bool:
        """True if this node represents a single file."""
        
    @abstractmethod
    def gather_contents(self) -> str:
        """Gather all file contents under this node."""

    # Concrete methods with default implementations
    def sort_children(self) -> None:
        """Sort children: README first, then files, then dirs, hidden last."""
        def _sort_key(child: FileSystemNode) -> tuple[int, str]:
            name = (child.name or "").lower()
            
            # README files get highest priority
            if name == "readme" or name.startswith("readme."):
                return (0, name)
            
            # Then sort by type and visibility
            if isinstance(child, FileSystemFile):
                return (1 if not name.startswith(".") else 2, name)
            else:  # Directories, symlinks
                return (3 if not name.startswith(".") else 4, name)

        self.children.sort(key=_sort_key)

    @property
    def content_string(self) -> str:
        """Content with header for output format."""
        parts = [
            SEPARATOR,
            f"{self.node_type}: {str(self.path_str or '').replace(os.sep, '/')}",
            SEPARATOR,
            f"{self.content}",
        ]
        return "\n".join(parts) + "\n\n"

    def get_content(self) -> str:
        """Default content reading with encoding detection."""
        from gitingest.utils.file_utils import _decodes, _get_preferred_encodings, _read_chunk
        from gitingest.utils.notebook import process_notebook

        if not self.path:
            return "Error: No path specified"

        # Handle notebooks specially
        if self.path.suffix == ".ipynb":
            try:
                return process_notebook(self.path)
            except Exception as exc:
                return f"Error processing notebook: {exc}"

        # Read chunk and detect encoding
        chunk = _read_chunk(self.path)
        if chunk is None:
            return "Error reading file"
        if chunk == b"":
            return "[Empty file]"
        if not _decodes(chunk, "utf-8"):
            return "[Binary file]"

        # Find working encoding
        good_enc = next(
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

    @property
    def content(self) -> str:
        """Backward compatibility property."""
        return self.get_content()


@dataclass
class FileSystemFile(FileSystemNode):
    """Represents a file in the filesystem."""
    
    @property
    def display_name(self) -> str:
        """Files show just their name."""
        return self.name or ""
    
    @property
    def node_type(self) -> str:
        """File type identifier."""
        return "FILE"
    
    @property
    def is_single_file(self) -> bool:
        """Files are single files."""
        return True
    
    def gather_contents(self) -> str:
        """Files return their content string."""
        return self.content_string


@dataclass
class FileSystemDirectory(FileSystemNode):
    """Represents a directory in the filesystem."""

    file_count_total: int = 0
    
    @property
    def display_name(self) -> str:
        """Directories get trailing slash."""
        return (self.name or "") + "/"
    
    @property
    def node_type(self) -> str:
        """Directory type identifier."""
        return "DIRECTORY"
    
    @property
    def is_single_file(self) -> bool:
        """Directories are not single files."""
        return False
    
    def gather_contents(self) -> str:
        """Recursively gather all child contents."""
        return "\n".join(child.gather_contents() for child in self.children)

    def get_content(self) -> str:
        """Directories cannot have content."""
        raise ValueError("Cannot read content of a directory node")


@dataclass
class FileSystemSymlink(FileSystemNode):
    """Represents a symbolic link in the filesystem."""

    target: str = ""
    
    @property
    def display_name(self) -> str:
        """Symlinks show target."""
        return f"{self.name or ''} -> {self.target}"
    
    @property
    def node_type(self) -> str:
        """Symlink type identifier."""
        return "SYMLINK"
    
    @property
    def is_single_file(self) -> bool:
        """Symlinks are not single files."""
        return False
    
    def gather_contents(self) -> str:
        """Symlinks return their content string."""
        return self.content_string

    def get_content(self) -> str:
        """Symlinks content is their target."""
        return self.target


@dataclass
class GitRepository(FileSystemDirectory):
    """A directory that contains a .git folder, representing a Git repository."""

    git_info: dict = field(default_factory=dict)
    
    @property
    def display_name(self) -> str:
        """Git repos show as special directories."""
        return f"{self.name or ''}/ (git repository)"
    
    @property
    def node_type(self) -> str:
        """Git repository type identifier."""
        return "GIT_REPOSITORY"
