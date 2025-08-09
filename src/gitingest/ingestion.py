"""Functions to ingest and analyze a codebase directory or single file."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from gitingest.config import MAX_DIRECTORY_DEPTH, MAX_FILES, MAX_TOTAL_SIZE_BYTES
from gitingest.output_formatter import format_node
from gitingest.schemas import FileSystemNode, FileSystemNodeType, FileSystemStats
from gitingest.utils.ingestion_utils import _should_exclude, _should_include
from gitingest.utils.logging_config import get_logger

if TYPE_CHECKING:
    from gitingest.schemas import IngestionQuery

# Initialize logger for this module
logger = get_logger(__name__)


def ingest_query(query: IngestionQuery) -> tuple[str, str, str]:
    """Run the ingestion process for a parsed query.

    This is the main entry point for analyzing a codebase directory or single file. It processes the query
    parameters, reads the file or directory content, and generates a summary, directory structure, and file content,
    along with token estimations.

    Parameters
    ----------
    query : IngestionQuery
        The parsed query object containing information about the repository and query parameters.

    Returns
    -------
    tuple[str, str, str]
        A tuple containing the summary, directory structure, and file contents.

    Raises
    ------
    ValueError
        If the path cannot be found, is not a file, or the file has no content.

    """
    logger.info(
        "Starting file ingestion",
        extra={
            "slug": query.slug,
            "subpath": query.subpath,
            "local_path": str(query.local_path),
            "max_file_size": query.max_file_size,
        },
    )

    subpath = Path(query.subpath.strip("/")).as_posix()
    path = query.local_path / subpath

    if not path.exists():
        logger.error("Path not found", extra={"path": str(path), "slug": query.slug})
        msg = f"{query.slug} cannot be found"
        raise ValueError(msg)

    if (query.type and query.type == "blob") or query.local_path.is_file():
        # TODO: We do this wrong! We should still check the branch and commit!
        logger.info("Processing single file", extra={"file_path": str(path)})

        if not path.is_file():
            logger.error("Expected file but found non-file", extra={"path": str(path)})
            msg = f"Path {path} is not a file"
            raise ValueError(msg)

        relative_path = path.relative_to(query.local_path)

        file_node = FileSystemNode(
            name=path.name,
            type=FileSystemNodeType.FILE,
            size=path.stat().st_size,
            file_count=1,
            path_str=str(relative_path),
            path=path,
        )

        if not file_node.content:
            logger.error("File has no content", extra={"file_name": file_node.name})
            msg = f"File {file_node.name} has no content"
            raise ValueError(msg)

        logger.info(
            "Single file processing completed",
            extra={
                "file_name": file_node.name,
                "file_size": file_node.size,
            },
        )
        return format_node(file_node, query=query)

    logger.info("Processing directory", extra={"directory_path": str(path)})

    root_node = FileSystemNode(
        name=path.name,
        type=FileSystemNodeType.DIRECTORY,
        path_str=str(path.relative_to(query.local_path)),
        path=path,
    )

    stats = FileSystemStats()

    _process_node(node=root_node, query=query, stats=stats)

    logger.info(
        "Directory processing completed",
        extra={
            "total_files": root_node.file_count,
            "total_directories": root_node.dir_count,
            "total_size_bytes": root_node.size,
            "stats_total_files": stats.total_files,
            "stats_total_size": stats.total_size,
        },
    )

    return format_node(root_node, query=query)


def _process_node(node: FileSystemNode, query: IngestionQuery, stats: FileSystemStats) -> None:
    """Process a file or directory item within a directory.

    This function handles each file or directory item, checking if it should be included or excluded based on the
    provided patterns. It handles symlinks, directories, and files accordingly.

    Parameters
    ----------
    node : FileSystemNode
        The current directory or file node being processed.
    query : IngestionQuery
        The parsed query object containing information about the repository and query parameters.
    stats : FileSystemStats
        Statistics tracking object for the total file count and size.

    """
    if limit_exceeded(stats, depth=node.depth):
        return

    for sub_path in node.path.iterdir():
        if query.ignore_patterns and _should_exclude(sub_path, query.local_path, query.ignore_patterns):
            continue

        if query.include_patterns and not _should_include(sub_path, query.local_path, query.include_patterns):
            continue

        if sub_path.is_symlink():
            _process_symlink(path=sub_path, parent_node=node, stats=stats, local_path=query.local_path)
        elif sub_path.is_file():
            if sub_path.stat().st_size > query.max_file_size:
                logger.debug(
                    "Skipping file: would exceed max file size limit",
                    extra={
                        "file_path": str(sub_path),
                        "file_size": sub_path.stat().st_size,
                        "max_file_size": query.max_file_size,
                    },
                )
                continue
            _process_file(path=sub_path, parent_node=node, stats=stats, local_path=query.local_path)
        elif sub_path.is_dir():
            child_directory_node = FileSystemNode(
                name=sub_path.name,
                type=FileSystemNodeType.DIRECTORY,
                path_str=str(sub_path.relative_to(query.local_path)),
                path=sub_path,
                depth=node.depth + 1,
            )

            _process_node(node=child_directory_node, query=query, stats=stats)

            if not child_directory_node.children:
                continue

            node.children.append(child_directory_node)
            node.size += child_directory_node.size
            node.file_count += child_directory_node.file_count
            node.dir_count += 1 + child_directory_node.dir_count
        else:
            logger.warning("Unknown file type, skipping", extra={"file_path": str(sub_path)})

    node.sort_children()


def _process_symlink(path: Path, parent_node: FileSystemNode, stats: FileSystemStats, local_path: Path) -> None:
    """Process a symlink in the file system.

    This function checks the symlink's target.

    Parameters
    ----------
    path : Path
        The full path of the symlink.
    parent_node : FileSystemNode
        The parent directory node.
    stats : FileSystemStats
        Statistics tracking object for the total file count and size.
    local_path : Path
        The base path of the repository or directory being processed.

    """
    child = FileSystemNode(
        name=path.name,
        type=FileSystemNodeType.SYMLINK,
        path_str=str(path.relative_to(local_path)),
        path=path,
        depth=parent_node.depth + 1,
    )
    stats.total_files += 1
    parent_node.children.append(child)
    parent_node.file_count += 1


def _process_file(path: Path, parent_node: FileSystemNode, stats: FileSystemStats, local_path: Path) -> None:
    """Process a file in the file system.

    This function checks the file's size, increments the statistics, and reads its content.
    If the file size exceeds the maximum allowed, it raises an error.

    Parameters
    ----------
    path : Path
        The full path of the file.
    parent_node : FileSystemNode
        The dictionary to accumulate the results.
    stats : FileSystemStats
        Statistics tracking object for the total file count and size.
    local_path : Path
        The base path of the repository or directory being processed.

    """
    if stats.total_files + 1 > MAX_FILES:
        logger.warning(
            "Maximum file limit reached",
            extra={
                "current_files": stats.total_files,
                "max_files": MAX_FILES,
                "file_path": str(path),
            },
        )
        return

    file_size = path.stat().st_size
    if stats.total_size + file_size > MAX_TOTAL_SIZE_BYTES:
        logger.warning(
            "Skipping file: would exceed total size limit",
            extra={
                "file_path": str(path),
                "file_size": file_size,
                "current_total_size": stats.total_size,
                "max_total_size": MAX_TOTAL_SIZE_BYTES,
            },
        )
        return

    stats.total_files += 1
    stats.total_size += file_size

    child = FileSystemNode(
        name=path.name,
        type=FileSystemNodeType.FILE,
        size=file_size,
        file_count=1,
        path_str=str(path.relative_to(local_path)),
        path=path,
        depth=parent_node.depth + 1,
    )

    parent_node.children.append(child)
    parent_node.size += file_size
    parent_node.file_count += 1


def limit_exceeded(stats: FileSystemStats, depth: int) -> bool:
    """Check if any of the traversal limits have been exceeded.

    This function checks if the current traversal has exceeded any of the configured limits:
    maximum directory depth, maximum number of files, or maximum total size in bytes.

    Parameters
    ----------
    stats : FileSystemStats
        Statistics tracking object for the total file count and size.
    depth : int
        The current depth of directory traversal.

    Returns
    -------
    bool
        ``True`` if any limit has been exceeded, ``False`` otherwise.

    """
    if depth > MAX_DIRECTORY_DEPTH:
        logger.warning(
            "Maximum directory depth limit reached",
            extra={
                "current_depth": depth,
                "max_depth": MAX_DIRECTORY_DEPTH,
            },
        )
        return True

    if stats.total_files >= MAX_FILES:
        logger.warning(
            "Maximum file limit reached",
            extra={
                "current_files": stats.total_files,
                "max_files": MAX_FILES,
            },
        )
        return True  # TODO: end recursion

    if stats.total_size >= MAX_TOTAL_SIZE_BYTES:
        logger.warning(
            "Maximum total size limit reached",
            extra={
                "current_size_mb": stats.total_size / 1024 / 1024,
                "max_size_mb": MAX_TOTAL_SIZE_BYTES / 1024 / 1024,
            },
        )
        return True  # TODO: end recursion

    return False
