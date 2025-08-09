"""Process a query by parsing input, cloning a repository, and generating a summary."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, cast

from gitingest.clone import clone_repo
from gitingest.ingestion import ingest_query
from gitingest.query_parser import parse_remote_repo
from gitingest.utils.git_utils import resolve_commit, validate_github_token
from gitingest.utils.logging_config import get_logger
from gitingest.utils.pattern_utils import process_patterns
from server.models import IngestErrorResponse, IngestResponse, IngestSuccessResponse, PatternType, S3Metadata
from server.s3_utils import (
    _build_s3_url,
    check_s3_object_exists,
    generate_s3_file_path,
    get_metadata_from_s3,
    is_s3_enabled,
    upload_metadata_to_s3,
    upload_to_s3,
)
from server.server_config import MAX_DISPLAY_SIZE

# Initialize logger for this module
logger = get_logger(__name__)

if TYPE_CHECKING:
    from gitingest.schemas.cloning import CloneConfig
    from gitingest.schemas.ingestion import IngestionQuery


def _cleanup_repository(clone_config: CloneConfig) -> None:
    """Clean up the cloned repository after processing."""
    try:
        local_path = Path(clone_config.local_path)
        if local_path.exists():
            shutil.rmtree(local_path)
            logger.info("Successfully cleaned up repository", extra={"local_path": str(local_path)})
    except (PermissionError, OSError):
        logger.exception("Could not delete repository", extra={"local_path": str(clone_config.local_path)})


async def _check_s3_cache(
    query: IngestionQuery,
    input_text: str,
    max_file_size: int,
    pattern_type: str,
    pattern: str,
    token: str | None,
) -> IngestSuccessResponse | None:
    """Check if digest already exists on S3 and return response if found.

    Parameters
    ----------
    query : IngestionQuery
        The parsed query object.
    input_text : str
        Original input text.
    max_file_size : int
        Maximum file size in KB.
    pattern_type : str
        Pattern type (include/exclude).
    pattern : str
        Pattern string.
    token : str | None
        GitHub token.

    Returns
    -------
    IngestSuccessResponse | None
        Response if file exists on S3, None otherwise.

    """
    if not is_s3_enabled():
        return None

    try:
        # Use git ls-remote to get commit SHA without cloning
        clone_config = query.extract_clone_config()
        logger.info("Resolving commit for S3 cache check", extra={"repo_url": query.url})
        query.commit = await resolve_commit(clone_config, token=token)
        logger.info("Commit resolved successfully", extra={"repo_url": query.url, "commit": query.commit})

        # Generate S3 file path using the resolved commit
        s3_file_path = generate_s3_file_path(
            source=query.url,
            user_name=cast("str", query.user_name),
            repo_name=cast("str", query.repo_name),
            commit=query.commit,
            subpath=query.subpath,
            include_patterns=query.include_patterns,
            ignore_patterns=query.ignore_patterns,
        )

        # Check if file exists on S3
        if check_s3_object_exists(s3_file_path):
            # File exists on S3, serve it directly without cloning
            s3_url = _build_s3_url(s3_file_path)
            query.s3_url = s3_url

            short_repo_url = f"{query.user_name}/{query.repo_name}"

            # Try to get cached metadata
            metadata = get_metadata_from_s3(s3_file_path)

            if metadata:
                # Use cached metadata if available
                summary = metadata.summary
                tree = metadata.tree
                content = metadata.content
            else:
                # Fallback to placeholder messages if metadata not available
                summary = "Digest served from cache (S3). Download the full digest to see content details."
                tree = "Digest served from cache. Download the full digest to see the file tree."
                content = "Digest served from cache. Download the full digest to see the content."

            return IngestSuccessResponse(
                repo_url=input_text,
                short_repo_url=short_repo_url,
                summary=summary,
                digest_url=s3_url,
                tree=tree,
                content=content,
                default_max_file_size=max_file_size,
                pattern_type=pattern_type,
                pattern=pattern,
            )
    except Exception as exc:
        # Log the exception but don't fail the entire request
        logger.warning("S3 cache check failed, falling back to normal cloning", extra={"error": str(exc)})

    logger.info("Digest not found in S3 cache, proceeding with normal cloning", extra={"repo_url": query.url})
    return None


def _store_digest_content(
    query: IngestionQuery,
    clone_config: CloneConfig,
    digest_content: str,
    summary: str,
    tree: str,
    content: str,
) -> None:
    """Store digest content either to S3 or locally based on configuration.

    Parameters
    ----------
    query : IngestionQuery
        The query object containing repository information.
    clone_config : CloneConfig
        The clone configuration object.
    digest_content : str
        The complete digest content to store.
    summary : str
        The summary content for metadata.
    tree : str
        The tree content for metadata.
    content : str
        The file content for metadata.

    """
    if is_s3_enabled():
        # Upload to S3 instead of storing locally
        s3_file_path = generate_s3_file_path(
            source=query.url,
            user_name=cast("str", query.user_name),
            repo_name=cast("str", query.repo_name),
            commit=query.commit,
            subpath=query.subpath,
            include_patterns=query.include_patterns,
            ignore_patterns=query.ignore_patterns,
        )
        s3_url = upload_to_s3(content=digest_content, s3_file_path=s3_file_path, ingest_id=query.id)

        # Also upload metadata JSON for caching
        metadata = S3Metadata(
            summary=summary,
            tree=tree,
            content=content,
        )
        try:
            upload_metadata_to_s3(metadata=metadata, s3_file_path=s3_file_path, ingest_id=query.id)
            logger.info("Successfully uploaded metadata to S3")
        except Exception as metadata_exc:
            # Log the error but don't fail the entire request
            logger.warning("Failed to upload metadata to S3", extra={"error": str(metadata_exc)})

        # Store S3 URL in query for later use
        query.s3_url = s3_url
    else:
        # Store locally
        local_txt_file = Path(clone_config.local_path).with_suffix(".txt")
        with local_txt_file.open("w", encoding="utf-8") as f:
            f.write(digest_content)


def _generate_digest_url(query: IngestionQuery) -> str:
    """Generate the digest URL based on S3 configuration.

    Parameters
    ----------
    query : IngestionQuery
        The query object containing repository information.

    Returns
    -------
    str
        The digest URL.

    Raises
    ------
    RuntimeError
        If S3 is enabled but no S3 URL was generated.

    """
    if is_s3_enabled():
        digest_url = getattr(query, "s3_url", None)
        if not digest_url:
            # This should not happen if S3 upload was successful
            msg = "S3 is enabled but no S3 URL was generated"
            raise RuntimeError(msg)
        return digest_url
    return f"/api/download/file/{query.id}"


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
    if token:
        validate_github_token(token)

    try:
        query = await parse_remote_repo(input_text, token=token)
    except Exception as exc:
        logger.warning("Failed to parse remote repository", extra={"input_text": input_text, "error": str(exc)})
        return IngestErrorResponse(error=str(exc))

    query.url = cast("str", query.url)
    query.max_file_size = max_file_size * 1024  # Convert to bytes since we currently use KB in higher levels
    query.ignore_patterns, query.include_patterns = process_patterns(
        exclude_patterns=pattern if pattern_type == PatternType.EXCLUDE else None,
        include_patterns=pattern if pattern_type == PatternType.INCLUDE else None,
    )

    # Check if digest already exists on S3 before cloning
    s3_response = await _check_s3_cache(
        query=query,
        input_text=input_text,
        max_file_size=max_file_size,
        pattern_type=pattern_type.value,
        pattern=pattern,
        token=token,
    )
    if s3_response:
        return s3_response

    clone_config = query.extract_clone_config()
    await clone_repo(clone_config, token=token)

    short_repo_url = f"{query.user_name}/{query.repo_name}"

    # The commit hash should always be available at this point
    if not query.commit:
        msg = "Unexpected error: no commit hash found"
        raise RuntimeError(msg)

    try:
        summary, tree, content = ingest_query(query)
        digest_content = tree + "\n" + content
        _store_digest_content(query, clone_config, digest_content, summary, tree, content)
    except Exception as exc:
        _print_error(query.url, exc, max_file_size, pattern_type, pattern)
        # Clean up repository even if processing failed
        _cleanup_repository(clone_config)
        return IngestErrorResponse(error=f"{exc!s}")

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

    digest_url = _generate_digest_url(query)

    # Clean up the repository after successful processing
    _cleanup_repository(clone_config)

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
    logger.info(
        "Processing query",
        extra={
            "url": url,
            "max_file_size_kb": int(max_file_size / 1024),
            "pattern_type": pattern_type,
            "pattern": pattern,
            "custom_size": int(max_file_size / 1024) != default_max_file_kb,
        },
    )


def _print_error(url: str, exc: Exception, max_file_size: int, pattern_type: str, pattern: str) -> None:
    """Print a formatted error message for debugging.

    Parameters
    ----------
    url : str
        The URL associated with the query that caused the error.
    exc : Exception
        The exception raised during the query or process.
    max_file_size : int
        The maximum file size allowed for the query, in bytes.
    pattern_type : str
        Specifies the type of pattern to use, either "include" or "exclude".
    pattern : str
        The actual pattern string to include or exclude in the query.

    """
    logger.error(
        "Query processing failed",
        extra={
            "url": url,
            "max_file_size_kb": int(max_file_size / 1024),
            "pattern_type": pattern_type,
            "pattern": pattern,
            "error": str(exc),
        },
    )


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
    logger.info(
        "Query processing completed successfully",
        extra={
            "url": url,
            "max_file_size_kb": int(max_file_size / 1024),
            "pattern_type": pattern_type,
            "pattern": pattern,
            "estimated_tokens": estimated_tokens,
        },
    )
