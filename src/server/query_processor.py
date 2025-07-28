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
    logger.debug(
        "Processing query: input_text=%s, slider_position=%s, pattern_type=%s, pattern=%s",
        input_text,
        slider_position,
        pattern_type,
        pattern,
    )
    if token:
        logger.debug("Validating GitHub token.")
        validate_github_token(token)

    max_file_size = log_slider_to_size(slider_position)
    logger.debug("Calculated max_file_size: %s", max_file_size)

    try:
        logger.debug("Parsing remote repo.")
        query = await parse_remote_repo(input_text, token=token)
        logger.debug("Parsed query: url=%s, user=%s, repo=%s", query.url, query.user_name, query.repo_name)
    except Exception as exc:
        logger.exception("Failed to parse remote repo.")
        return IngestErrorResponse(error=str(exc))

    query.url = cast("str", query.url)
    query.host = cast("str", query.host)
    query.max_file_size = max_file_size
    logger.debug("Processing patterns: pattern_type=%s, pattern=%s", pattern_type, pattern)
    query.ignore_patterns, query.include_patterns = process_patterns(
        exclude_patterns=pattern if pattern_type == PatternType.EXCLUDE else None,
        include_patterns=pattern if pattern_type == PatternType.INCLUDE else None,
    )

    clone_config = query.extract_clone_config()
    logger.debug("Cloning repo with config: %r", clone_config)
    await clone_repo(clone_config, token=token)

    short_repo_url = f"{query.user_name}/{query.repo_name}"  # Sets the "<user>/<repo>" for the page title

    try:
        logger.debug("Running ingest_query.")
        summary, tree, content = ingest_query(query)
        logger.debug("Ingest query complete. Writing tree and content to file.")
        # TODO: why are we writing the tree and content to a file here?
        local_txt_file = Path(clone_config.local_path).with_suffix(".txt")
        with local_txt_file.open("w", encoding="utf-8") as f:
            f.write(tree + "\n" + content)
        logger.debug("Wrote output to %s", local_txt_file)

    except Exception as exc:
        logger.exception(
            "Error processing query for URL %s (max_file_size=%s, pattern_type=%s, pattern=%s).",
            query.url,
            max_file_size,
            pattern_type,
            pattern,
            exc_info=exc,
        )
        return IngestErrorResponse(error=str(exc))

    if len(content) > MAX_DISPLAY_SIZE:
        logger.info(
            "Content cropped to %sk characters for display.",
            int(MAX_DISPLAY_SIZE / 1_000),
        )  # Important: user-facing truncation
        content = (
            f"(Files content cropped to {int(MAX_DISPLAY_SIZE / 1_000)}k characters, "
            "download full ingest to see more)\n" + content[:MAX_DISPLAY_SIZE]
        )

    logger.info(
        "Query processed successfully for URL %s (max_file_size=%s, pattern_type=%s, pattern=%s)",
        query.url,
        max_file_size,
        pattern_type,
        pattern,
    )  # Important: successful query
    estimated_tokens = None
    if "Estimated tokens:" in summary:
        estimated_tokens = summary[summary.index("Estimated tokens:") + len("Estimated ") :]
        logger.info("Estimated tokens: %s", estimated_tokens)  # Important: token estimation

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
