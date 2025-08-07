"""Schema for the filesystem representation."""

from __future__ import annotations

import os
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
class FileSystemNode(Source):  # pylint: disable=too-many-instance-attributes
    """Base class for filesystem nodes (files, directories, symlinks)."""

    name: str = ""
    path_str: str = ""
    path: Path | None = None
    size: int = 0
    file_count: int = 0
    dir_count: int = 0
    depth: int = 0
    children: list[FileSystemNode] = field(default_factory=list)

    @property
    def tree(self) -> str:
        """Return the name of this node."""
        return self.name

    def render_tree(self, prefix: str = "", *, is_last: bool = True) -> list[str]:
        """Return default tree representation with just the name."""
        current_prefix = "└── " if is_last else "├── "
        return [f"{prefix}{current_prefix}{self.name}"]

    def sort_children(self) -> None:
        """Sort the children nodes of a directory according to a specific order."""

        def _sort_key(child: FileSystemNode) -> tuple[int, str]:
            name = child.name.lower()
            # Each child knows its own sort priority - polymorphism!
            priority = child.get_sort_priority()
            if priority == 0 and (name == "readme" or name.startswith("readme.")):
                return (0, name)
            if priority == 0:  # Files
                return (1 if not name.startswith(".") else 2, name)
            # Directories, symlinks, etc.
            return (3 if not name.startswith(".") else 4, name)

        self.children.sort(key=_sort_key)

    def get_sort_priority(self) -> int:
        """Return sort priority. Override in subclasses."""
        return 1  # Default: not a file

    @property
    def content_string(self) -> str:
        """Return the content of the node as a string, including path and content.

        Returns
        -------
        str
            A string representation of the node's content.

        """
        type_name = self.__class__.__name__.upper().replace("FILESYSTEM", "")

        parts = [
            SEPARATOR,
            f"{type_name}: {str(self.path_str).replace(os.sep, '/')}",
            SEPARATOR,
            f"{self.content}",
        ]

        return "\n".join(parts) + "\n\n"

    def get_content(self) -> str:
        """Return file content. Override in subclasses for specific behavior."""
        if self.path is None:
            return "Error: No path specified"

        try:
            return self.path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading content of {self.name}: {e}"

    def get_summary_info(self) -> str:
        """Return summary information. Override in subclasses."""
        return ""

    def is_single_file(self) -> bool:
        """Return whether this node represents a single file."""
        return False

    def gather_contents(self) -> str:
        """Gather file contents. Override in subclasses."""
        return self.content_string

    def get_display_name(self) -> str:
        """Get display name for tree view. Override in subclasses."""
        return self.name

    def has_children(self) -> bool:
        """Return whether this node has children to display."""
        return False

    @property
    def content(self) -> str:
        """Return file content (simplified version for backward compatibility)."""
        return self.get_content()


@dataclass
class FileSystemFile(FileSystemNode):
    """Represents a file in the filesystem."""

    def get_sort_priority(self) -> int:
        """Files have priority 0 for sorting."""
        return 0

    def get_summary_info(self) -> str:
        """Return file summary information."""
        return f"File: {self.name}\nLines: {len(self.content.splitlines()):,}\n"

    def is_single_file(self) -> bool:
        """Files are single files."""
        return True

    def render_tree(self, prefix: str = "", *, is_last: bool = True) -> list[str]:
        """Render the tree representation of this file."""
        current_prefix = "└── " if is_last else "├── "
        return [f"{prefix}{current_prefix}{self.name}"]


@dataclass
class FileSystemDirectory(FileSystemNode):
    """Represents a directory in the filesystem."""

    file_count_total: int = 0

    def get_content(self) -> str:
        """Directories cannot have content."""
        msg = "Cannot read content of a directory node"
        raise ValueError(msg)

    def get_summary_info(self) -> str:
        """Return directory summary information."""
        return f"Files analyzed: {self.file_count}\n"

    def gather_contents(self) -> str:
        """Recursively gather contents of all files under this directory."""
        return "\n".join(child.gather_contents() for child in self.children)

    def get_display_name(self) -> str:
        """Directories get a trailing slash."""
        return self.name + "/"

    def has_children(self) -> bool:
        """Directories have children if the list is not empty."""
        return bool(self.children)

    def render_tree(self, prefix: str = "", *, is_last: bool = True) -> list[str]:
        """Render the tree representation of this directory."""
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
    def tree(self) -> str:
        """Return the tree representation of this directory."""
        return "\n".join(self.render_tree())


@dataclass
class GitRepository(FileSystemDirectory):
    """A directory that contains a .git folder, representing a Git repository."""

    git_info: dict = field(default_factory=dict)  # Store git metadata like branch, commit, etc.

    def render_tree(self, prefix: str = "", *, is_last: bool = True) -> list[str]:
        """Render the tree representation of this git repository."""
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
    """Represents a symbolic link in the filesystem."""

    target: str = ""
    # Add symlink-specific fields if needed

    def get_content(self) -> str:
        """Symlinks content is what they point to."""
        return self.target

    def get_display_name(self) -> str:
        """Symlinks show target."""
        return f"{self.name} -> {self.target}"

    def render_tree(self, prefix: str = "", *, is_last: bool = True) -> list[str]:
        """Render the tree representation of this symlink."""
        current_prefix = "└── " if is_last else "├── "
        display_name = f"{self.name} -> {self.target}" if self.target else self.name
        return [f"{prefix}{current_prefix}{display_name}"]
