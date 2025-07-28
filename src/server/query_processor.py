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
from server.s3_utils import generate_s3_file_path, is_s3_enabled, upload_to_s3
from server.server_config import MAX_DISPLAY_SIZE

logger = logging.getLogger(__name__)


async def process_query(
    input_text: str,
    max_file_size: int,
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
    max_file_size : int
        Max file size in KB to be include in the digest.
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

    Raises
    ------
    RuntimeError
        If the commit hash is not found (should never happen).

    """
    logger.debug(
        "Processing query: input_text=%s, max_file_size=%s, pattern_type=%s, pattern=%s",
        input_text,
        max_file_size,
        pattern_type,
        pattern,
    )
    if token:
        validate_github_token(token)

    try:
        logger.debug("Parsing remote repo.")
        query = await parse_remote_repo(input_text, token=token)
        logger.debug("Parsed query: url=%s, user=%s, repo=%s", query.url, query.user_name, query.repo_name)
    except Exception as exc:
        logger.exception("Failed to parse remote repo.")
        return IngestErrorResponse(error=str(exc))

    query.url = cast("str", query.url)
    query.max_file_size = max_file_size * 1024  # Convert to bytes since we currently use KB in higher levels
    query.ignore_patterns, query.include_patterns = process_patterns(
        exclude_patterns=pattern if pattern_type == PatternType.EXCLUDE else None,
        include_patterns=pattern if pattern_type == PatternType.INCLUDE else None,
    )

    clone_config = query.extract_clone_config()
    logger.debug("Cloning repo with config: %r", clone_config)
    await clone_repo(clone_config, token=token)

    short_repo_url = f"{query.user_name}/{query.repo_name}"  # Sets the "<user>/<repo>" for the page title

    # The commit hash should always be available at this point
    if not query.commit:
        msg = "Unexpected error: no commit hash found"
        raise RuntimeError(msg)

    try:
        summary, tree, content = ingest_query(query)

        # Prepare the digest content (tree + content)
        digest_content = tree + "\n" + content

        # Store digest based on S3 configuration
        if is_s3_enabled():
            # Upload to S3 instead of storing locally
            s3_file_path = generate_s3_file_path(
                source=query.url,
                user_name=cast("str", query.user_name),
                repo_name=cast("str", query.repo_name),
                commit=query.commit,
                include_patterns=query.include_patterns,
                ignore_patterns=query.ignore_patterns,
            )
            s3_url = upload_to_s3(content=digest_content, s3_file_path=s3_file_path, ingest_id=query.id)
            # Store S3 URL in query for later use
            query.s3_url = s3_url
        else:
            # Store locally
            logger.debug("Ingest query complete. Writing tree and content to file.")
            local_txt_file = Path(clone_config.local_path).with_suffix(".txt")
            with local_txt_file.open("w", encoding="utf-8") as f:
                f.write(digest_content)
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

    # Generate digest_url based on S3 configuration
    if is_s3_enabled():
        digest_url = getattr(query, "s3_url", None)
        if not digest_url:
            # This should not happen if S3 upload was successful
            msg = "S3 is enabled but no S3 URL was generated"
            raise RuntimeError(msg)
    else:
        digest_url = f"/api/download/file/{query.id}"

    return IngestSuccessResponse(
        repo_url=input_text,
        short_repo_url=short_repo_url,
        summary=summary,
        digest_url=digest_url,
        tree=tree,
        content=content,
        default_max_file_size=max_file_size,
        pattern_type=pattern_type,
        pattern=pattern,
    )
