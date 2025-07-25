"""Process a query by parsing input, cloning a repository, and generating a summary."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from gitingest.clone import clone_repo
from gitingest.ingestion import ingest_query
from gitingest.query_parser import parse_remote_repo
from gitingest.utils.git_utils import validate_github_token
from gitingest.utils.pattern_utils import process_patterns
from server.models import IngestErrorResponse, IngestResponse, IngestSuccessResponse, PatternType
from server.server_config import MAX_DISPLAY_SIZE
from server.server_utils import log_slider_to_size

logger = logging.getLogger(__name__)


async def process_query(
    input_text: str,
    slider_position: int,
    pattern_type: PatternType,
    pattern: str,
    token: str | None = None,
) -> IngestResponse:
    """Process a query by parsing input, cloning a repository, and generating a summary.

    Handle user input, process Git repository data, and prepare
    a response for rendering a template with the processed results or an error message.

    Parameters
    ----------
    input_text : str
        Input text provided by the user, typically a Git repository URL or slug.
    slider_position : int
        Position of the slider, representing the maximum file size in the query.
    pattern_type : PatternType
        Type of pattern to use (either "include" or "exclude")
    pattern : str
        Pattern to include or exclude in the query, depending on the pattern type.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Returns
    -------
    IngestResponse
        A union type, corresponding to IngestErrorResponse or IngestSuccessResponse

    """
    if token:
        validate_github_token(token)

    max_file_size = log_slider_to_size(slider_position)

    try:
        query = await parse_remote_repo(input_text, token=token)
    except Exception as exc:
        logger.exception()
        return IngestErrorResponse(error=str(exc))

    query.url = cast("str", query.url)
    query.host = cast("str", query.host)
    query.max_file_size = max_file_size
    query.ignore_patterns, query.include_patterns = process_patterns(
        exclude_patterns=pattern if pattern_type == PatternType.EXCLUDE else None,
        include_patterns=pattern if pattern_type == PatternType.INCLUDE else None,
    )

    clone_config = query.extract_clone_config()
    await clone_repo(clone_config, token=token)

    short_repo_url = f"{query.user_name}/{query.repo_name}"  # Sets the "<user>/<repo>" for the page title

    try:
        summary, tree, content = ingest_query(query)

        # TODO: why are we writing the tree and content to a file here?
        local_txt_file = Path(clone_config.local_path).with_suffix(".txt")
        with local_txt_file.open("w", encoding="utf-8") as f:
            f.write(tree + "\n" + content)

    except Exception as exc:
        logger.exception()
        _print_error(query.url, max_file_size, pattern_type, pattern)
        return IngestErrorResponse(error=str(exc))

    if len(content) > MAX_DISPLAY_SIZE:
        content = (
            f"(Files content cropped to {int(MAX_DISPLAY_SIZE / 1_000)}k characters, "
            "download full ingest to see more)\n" + content[:MAX_DISPLAY_SIZE]
        )

    _print_success(
        url=query.url,
        max_file_size=max_file_size,
        pattern_type=pattern_type,
        pattern=pattern,
        summary=summary,
    )

    return IngestSuccessResponse(
        repo_url=input_text,
        short_repo_url=short_repo_url,
        summary=summary,
        ingest_id=query.id,
        tree=tree,
        content=content,
        default_max_file_size=slider_position,
        pattern_type=pattern_type,
        pattern=pattern,
    )


def _print_query(url: str, max_file_size: int, pattern_type: str, pattern: str) -> None:
    """Print a formatted summary of the query details for debugging.

    Parameters
    ----------
    url : str
        The URL associated with the query.
    max_file_size : int
        The maximum file size allowed for the query, in bytes.
    pattern_type : str
        Specifies the type of pattern to use, either "include" or "exclude".
    pattern : str
        The actual pattern string to include or exclude in the query.

    """
    default_max_file_kb = 50
    logger.info("%s", url)
    if int(max_file_size / 1024) != default_max_file_kb:
        logger.info("Size: %ikB", int(max_file_size / 1024))
    if pattern_type == "include" and pattern != "":
        logger.info("Include %s", pattern)
    elif pattern_type == "exclude" and pattern != "":
        logger.info("Exclude %s", pattern)


def _print_error(url: str, max_file_size: int, pattern_type: str, pattern: str) -> None:
    """Print a formatted error message for debugging.

    Parameters
    ----------
    url : str
        The URL associated with the query that caused the error.
    max_file_size : int
        The maximum file size allowed for the query, in bytes.
    pattern_type : str
        Specifies the type of pattern to use, either "include" or "exclude".
    pattern : str
        The actual pattern string to include or exclude in the query.

    """
    _print_query(url, max_file_size, pattern_type, pattern)


def _print_success(url: str, max_file_size: int, pattern_type: str, pattern: str, summary: str) -> None:
    """Print a formatted success message for debugging.

    Parameters
    ----------
    url : str
        The URL associated with the successful query.
    max_file_size : int
        The maximum file size allowed for the query, in bytes.
    pattern_type : str
        Specifies the type of pattern to use, either "include" or "exclude".
    pattern : str
        The actual pattern string to include or exclude in the query.
    summary : str
        A summary of the query result, including details like estimated tokens.

    """
    estimated_tokens = summary[summary.index("Estimated tokens:") + len("Estimated ") :]
    _print_query(url, max_file_size, pattern_type, pattern)
    logger.info("%s", estimated_tokens)
