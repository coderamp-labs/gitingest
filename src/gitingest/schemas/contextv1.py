"""Schema for ContextV1 objects used in formatting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

from gitingest.schemas.filesystem import FileSystemDirectory, FileSystemNode, Source

if TYPE_CHECKING:
    from gitingest.schemas import IngestionQuery


@dataclass
class ContextV1:
    """The ContextV1 object is an object that contains all information needed to produce a formatted output.

    This object contains all information needed to produce a formatted output
    similar to the "legacy" output.

    Attributes
    ----------
    sources : list[Source]
        List of source objects (files, directories, etc.)
    query : IngestionQuery
        The query context.

    """

    sources: list[Source]
    query: IngestionQuery

    @property
    def sources_by_type(self) -> dict[str, list[Source]]:
        """Return sources grouped by their class name."""
        result = {}
        for source in self.sources:
            class_name = source.__class__.__name__
            if class_name not in result:
                result[class_name] = []
            result[class_name].append(source)
        return result

    def __getitem__(self, key: str) -> list[Source]:
        """Allow dict-like access to sources by type name."""
        sources_dict = self.sources_by_type
        if key not in sources_dict:
            error_msg = f"No sources of type '{key}' found"
            raise KeyError(error_msg)
        return sources_dict[key]

    def __iter__(self) -> Iterator[Source]:
        """Allow iteration over all sources."""
        return iter(self.sources)

    @property
    def file_count(self) -> int:
        """Calculate total file count based on sources."""
        # No need to iterate on children, directories are already aware of their
        # file count
        total = 0
        for source in self.sources:
            if isinstance(source, FileSystemDirectory):
                # For directories, add their file_count
                total += source.file_count
            elif isinstance(source, FileSystemNode):
                # For individual files/nodes, increment by 1
                total += 1
        return total
