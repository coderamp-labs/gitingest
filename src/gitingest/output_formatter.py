"""Functions to ingest and analyze a codebase directory or single file."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from gitingest.schemas import FileSystemNode, FileSystemNodeType
from gitingest.utils.compat_func import readlink
from gitingest.utils.logging_config import get_logger
from gitingest.utils.memory_utils import force_garbage_collection, log_memory_stats
from gitingest.utils.token_utils import clear_encoding_cache, count_tokens_optimized, format_token_count

if TYPE_CHECKING:
    from gitingest.schemas import IngestionQuery

# Initialize logger for this module
logger = get_logger(__name__)


def format_node(node: FileSystemNode, query: IngestionQuery) -> tuple[str, str, str]:
    """Generate a summary, directory structure, and file contents for a given file system node.

    If the node represents a directory, the function will recursively process its contents.

    Parameters
    ----------
    node : FileSystemNode
        The file system node to be summarized.
    query : IngestionQuery
        The parsed query object containing information about the repository and query parameters.

    Returns
    -------
    tuple[str, str, str]
        A tuple containing the summary, directory structure, and file contents.

    """
    is_single_file = node.type == FileSystemNodeType.FILE
    summary = _create_summary_prefix(query, single_file=is_single_file)

    if node.type == FileSystemNodeType.DIRECTORY:
        summary += f"Files analyzed: {node.file_count}\n"
    elif node.type == FileSystemNodeType.FILE:
        summary += f"File: {node.name}\n"
        summary += f"Lines: {len(node.content.splitlines()):,}\n"

    # Log memory before tree generation
    log_memory_stats("before tree structure generation")

    tree = "Directory structure:\n" + _create_tree_structure(query, node=node)

    # Log memory before content gathering (this is the memory-intensive part)
    log_memory_stats("before content gathering")

    content = _gather_file_contents(node)

    # Force garbage collection after content gathering
    force_garbage_collection()
    log_memory_stats("after content gathering and cleanup")

    # Count tokens with optimization
    token_count = count_tokens_optimized(tree + content)
    if token_count > 0:
        summary += f"\nEstimated tokens: {format_token_count(token_count)}"

    # Final cleanup
    if hasattr(node, "clear_content_cache_recursive"):
        node.clear_content_cache_recursive()

    # Clear the tiktoken encoding cache to free memory
    clear_encoding_cache()
    force_garbage_collection()
    log_memory_stats("after final cache and encoding cleanup")

    return summary, tree, content


def _create_summary_prefix(query: IngestionQuery, *, single_file: bool = False) -> str:
    """Create a prefix string for summarizing a repository or local directory.

    Includes repository name (if provided), commit/branch details, and subpath if relevant.

    Parameters
    ----------
    query : IngestionQuery
        The parsed query object containing information about the repository and query parameters.
    single_file : bool
        A flag indicating whether the summary is for a single file (default: ``False``).

    Returns
    -------
    str
        A summary prefix string containing repository, commit, branch, and subpath details.

    """
    parts = []

    if query.user_name:
        parts.append(f"Repository: {query.user_name}/{query.repo_name}")
    else:
        # Local scenario
        parts.append(f"Directory: {query.slug}")

    if query.tag:
        parts.append(f"Tag: {query.tag}")
    elif query.branch and query.branch not in ("main", "master"):
        parts.append(f"Branch: {query.branch}")

    if query.commit:
        parts.append(f"Commit: {query.commit}")

    if query.subpath != "/" and not single_file:
        parts.append(f"Subpath: {query.subpath}")

    return "\n".join(parts) + "\n"


def _gather_file_contents(node: FileSystemNode) -> str:
    """Recursively gather contents of all files under the given node.

    This function recursively processes a directory node and gathers the contents of all files
    under that node. It returns the concatenated content of all files as a single string.

    Parameters
    ----------
    node : FileSystemNode
        The current directory or file node being processed.

    Returns
    -------
    str
        The concatenated content of all files under the given node.

    """
    if node.type != FileSystemNodeType.DIRECTORY:
        return node.content_string

    # Use StringIO for memory-efficient string concatenation
    content_buffer = StringIO()
    try:
        _gather_file_contents_recursive(node, content_buffer)
        return content_buffer.getvalue()
    finally:
        content_buffer.close()


def _gather_file_contents_recursive(node: FileSystemNode, buffer: StringIO) -> None:
    """Recursively gather file contents with memory optimization.

    This version includes memory optimizations:
    - Progressive content cache clearing
    - Periodic garbage collection
    - Memory-aware processing

    Parameters
    ----------
    node : FileSystemNode
        The current directory or file node being processed.
    buffer : StringIO
        Buffer to write content to.

    """
    if node.type != FileSystemNodeType.DIRECTORY:
        # Write content and immediately clear cache to free memory
        buffer.write(node.content_string)
        node.clear_content_cache()
        return

    for files_processed, child in enumerate(node.children, 1):
        _gather_file_contents_recursive(child, buffer)

        # Progressive cleanup every 10 files to prevent memory accumulation
        if files_processed % 10 == 0:
            force_garbage_collection()

    # Clear content cache for this directory after processing all children
    node.clear_content_cache()


def _create_tree_structure(
    query: IngestionQuery,
    *,
    node: FileSystemNode,
    prefix: str = "",
    is_last: bool = True,
) -> str:
    """Generate a tree-like string representation of the file structure.

    This function generates a string representation of the directory structure, formatted
    as a tree with appropriate indentation for nested directories and files.

    Parameters
    ----------
    query : IngestionQuery
        The parsed query object containing information about the repository and query parameters.
    node : FileSystemNode
        The current directory or file node being processed.
    prefix : str
        A string used for indentation and formatting of the tree structure (default: ``""``).
    is_last : bool
        A flag indicating whether the current node is the last in its directory (default: ``True``).

    Returns
    -------
    str
        A string representing the directory structure formatted as a tree.

    """
    if not node.name:
        # If no name is present, use the slug as the top-level directory name
        node.name = query.slug

    tree_str = ""
    current_prefix = "└── " if is_last else "├── "

    # Indicate directories with a trailing slash
    display_name = node.name
    if node.type == FileSystemNodeType.DIRECTORY:
        display_name += "/"
    elif node.type == FileSystemNodeType.SYMLINK:
        display_name += " -> " + readlink(node.path).name

    tree_str += f"{prefix}{current_prefix}{display_name}\n"

    if node.type == FileSystemNodeType.DIRECTORY and node.children:
        prefix += "    " if is_last else "│   "
        for i, child in enumerate(node.children):
            tree_str += _create_tree_structure(query, node=child, prefix=prefix, is_last=i == len(node.children) - 1)
    return tree_str
