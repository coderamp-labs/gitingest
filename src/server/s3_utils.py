"""S3 utility functions for uploading and managing digest files."""

from __future__ import annotations

import hashlib
import logging
import os
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from uuid import UUID  # noqa: TC003 (typing-only-standard-library-import) needed for type checking (pydantic)

import boto3
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from botocore.client import BaseClient

# Initialize logger for this module
logger = logging.getLogger(__name__)


class S3UploadError(Exception):
    """Custom exception for S3 upload failures."""


def is_s3_enabled() -> bool:
    """Check if S3 is enabled via environment variables."""
    return os.getenv("S3_ENABLED", "false").lower() == "true"


def get_s3_config() -> dict[str, str | None]:
    """Get S3 configuration from environment variables."""
    config = {
        "endpoint_url": os.getenv("S3_ENDPOINT"),
        "aws_access_key_id": os.getenv("S3_ACCESS_KEY"),
        "aws_secret_access_key": os.getenv("S3_SECRET_KEY"),
        "region_name": os.getenv("S3_REGION") or os.getenv("AWS_REGION", "us-east-1"),
    }
    return {k: v for k, v in config.items() if v is not None}


def get_s3_bucket_name() -> str:
    """Get S3 bucket name from environment variables."""
    return os.getenv("S3_BUCKET_NAME", "gitingest-bucket")


def get_s3_alias_host() -> str | None:
    """Get S3 alias host for public URLs."""
    return os.getenv("S3_ALIAS_HOST")


def generate_s3_file_path(
    source: str,
    user_name: str,
    repo_name: str,
    commit: str,
    include_patterns: set[str] | None,
    ignore_patterns: set[str],
) -> str:
    """Generate S3 file path with proper naming convention.

    The file path is formatted as:
    [<S3_DIRECTORY_PREFIX>/]ingest/<provider>/<repo-owner>/<repo-name>/<branch>/<commit-ID>/<exclude&include hash>.txt

    If S3_DIRECTORY_PREFIX environment variable is set, it will be prefixed to the path.
    The commit-ID is always included in the URL.
    If no specific commit is provided, the actual commit hash from the cloned repository is used.

    Parameters
    ----------
    source : str
        Git host (e.g., github, gitlab, bitbucket, etc.).
    user_name : str
        Repository owner or user.
    repo_name : str
        Repository name.
    commit : str
        Commit hash.
    include_patterns : set[str] | None
        Set of patterns specifying which files to include.
    ignore_patterns : set[str]
        Set of patterns specifying which files to exclude.

    Returns
    -------
    str
        S3 file path string.

    Raises
    ------
    ValueError
        If the source URL is invalid.

    """
    hostname = urlparse(source).hostname
    if hostname is None:
        msg = "Invalid source URL"
        logger.error(msg)
        raise ValueError(msg)

    # Extract source from URL or default to "unknown"
    git_source = {
        "github.com": "github",
        "gitlab.com": "gitlab",
        "bitbucket.org": "bitbucket",
    }.get(hostname, "unknown")

    # Create hash of exclude/include patterns for uniqueness
    patterns_str = f"include:{sorted(include_patterns) if include_patterns else []}"
    patterns_str += f"exclude:{sorted(ignore_patterns)}"
    patterns_hash = hashlib.sha256(patterns_str.encode()).hexdigest()[:16]

    # Build the base path
    base_path = f"ingest/{git_source}/{user_name}/{repo_name}/{commit}/{patterns_hash}.txt"

    # Check for S3_DIRECTORY_PREFIX environment variable
    s3_directory_prefix = os.getenv("S3_DIRECTORY_PREFIX")

    if not s3_directory_prefix:
        return base_path

    # Remove trailing slash if present and add the prefix
    s3_directory_prefix = s3_directory_prefix.rstrip("/")
    return f"{s3_directory_prefix}/{base_path}"


def create_s3_client() -> BaseClient:
    """Create and return an S3 client with configuration from environment."""
    config = get_s3_config()
    # Log S3 client creation (excluding sensitive info)
    log_config = config.copy()
    has_credentials = bool(log_config.pop("aws_access_key_id", None) or log_config.pop("aws_secret_access_key", None))
    logger.debug(
        msg="Creating S3 client",
        extra={
            "s3_config": log_config,
            "has_credentials": has_credentials,
        },
    )
    return boto3.client("s3", **config)


def upload_to_s3(content: str, s3_file_path: str, ingest_id: UUID) -> str:
    """Upload content to S3 and return the public URL.

    This function uploads the provided content to an S3 bucket and returns the public URL for the uploaded file.
    The ingest ID is stored as an S3 object tag.

    Parameters
    ----------
    content : str
        The digest content to upload.
    s3_file_path : str
        The S3 file path where the content will be stored.
    ingest_id : UUID
        The ingest ID to store as an S3 object tag.

    Returns
    -------
    str
        Public URL to access the uploaded file.

    Raises
    ------
    ValueError
        If S3 is not enabled.
    S3UploadError
        If the upload to S3 fails.

    """
    if not is_s3_enabled():
        msg = "S3 is not enabled"
        logger.error(msg)
        raise ValueError(msg)

    s3_client = create_s3_client()
    bucket_name = get_s3_bucket_name()

    extra_fields = {
        "bucket_name": bucket_name,
        "s3_file_path": s3_file_path,
        "ingest_id": str(ingest_id),
        "content_size": len(content),
    }

    # Log upload attempt
    logger.debug("Starting S3 upload", extra=extra_fields)

    try:
        # Upload the content with ingest_id as tag
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_file_path,
            Body=content.encode("utf-8"),
            ContentType="text/plain",
            Tagging=f"ingest_id={ingest_id!s}",
        )
    except ClientError as err:
        # Log upload failure
        logger.exception(
            "S3 upload failed",
            extra={
                "bucket_name": bucket_name,
                "s3_file_path": s3_file_path,
                "ingest_id": str(ingest_id),
                "error_code": err.response.get("Error", {}).get("Code"),
                "error_message": str(err),
            },
        )
        msg = f"Failed to upload to S3: {err}"
        raise S3UploadError(msg) from err

    # Generate public URL
    alias_host = get_s3_alias_host()
    if alias_host:
        # Use alias host if configured
        public_url = f"{alias_host.rstrip('/')}/{s3_file_path}"
    else:
        # Fallback to direct S3 URL
        endpoint = get_s3_config().get("endpoint_url")
        if endpoint:
            public_url = f"{endpoint.rstrip('/')}/{bucket_name}/{s3_file_path}"
        else:
            public_url = f"https://{bucket_name}.s3.{get_s3_config()['region_name']}.amazonaws.com/{s3_file_path}"

    # Log successful upload
    logger.debug(
        "S3 upload completed successfully",
        extra={
            "bucket_name": bucket_name,
            "s3_file_path": s3_file_path,
            "ingest_id": str(ingest_id),
            "public_url": public_url,
        },
    )

    return public_url


def _build_s3_url(key: str) -> str:
    """Build S3 URL for a given key."""
    alias_host = get_s3_alias_host()
    if alias_host:
        return f"{alias_host.rstrip('/')}/{key}"

    bucket_name = get_s3_bucket_name()
    config = get_s3_config()

    endpoint = config["endpoint_url"]
    if endpoint:
        return f"{endpoint.rstrip('/')}/{bucket_name}/{key}"

    return f"https://{bucket_name}.s3.{config['region_name']}.amazonaws.com/{key}"


def _check_object_tags(s3_client: BaseClient, bucket_name: str, key: str, target_ingest_id: UUID) -> bool:
    """Check if an S3 object has the matching ingest_id tag."""
    try:
        tags_response = s3_client.get_object_tagging(Bucket=bucket_name, Key=key)
        tags = {tag["Key"]: tag["Value"] for tag in tags_response.get("TagSet", [])}
        return tags.get("ingest_id") == str(target_ingest_id)
    except ClientError:
        return False


def get_s3_url_for_ingest_id(ingest_id: UUID) -> str | None:
    """Get S3 URL for a given ingest ID if it exists.

    Search for files in S3 using object tags to find the matching ingest_id and returns the S3 URL if found.
    Used by the download endpoint to redirect to S3 if available.

    Parameters
    ----------
    ingest_id : UUID
        The ingest ID to search for in S3 object tags.

    Returns
    -------
    str | None
        S3 URL if file exists, None otherwise.

    """
    if not is_s3_enabled():
        logger.debug("S3 not enabled, skipping URL lookup for ingest_id: %s", ingest_id)
        return None

    logger.debug(msg="Starting S3 URL lookup for ingest ID", extra={"ingest_id": str(ingest_id)})

    try:
        s3_client = create_s3_client()
        bucket_name = get_s3_bucket_name()

        # List all objects in the ingest/ prefix and check their tags
        paginator = s3_client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=bucket_name, Prefix="ingest/")

        objects_checked = 0
        for page in page_iterator:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                key = obj["Key"]
                objects_checked += 1
                if _check_object_tags(
                    s3_client=s3_client,
                    bucket_name=bucket_name,
                    key=key,
                    target_ingest_id=ingest_id,
                ):
                    s3_url = _build_s3_url(key)
                    logger.debug(
                        msg="Found S3 object for ingest ID",
                        extra={
                            "ingest_id": str(ingest_id),
                            "s3_key": key,
                            "s3_url": s3_url,
                            "objects_checked": objects_checked,
                        },
                    )
                    return s3_url

        logger.debug(
            msg="No S3 object found for ingest ID",
            extra={
                "ingest_id": str(ingest_id),
                "objects_checked": objects_checked,
            },
        )

    except ClientError as err:
        logger.exception(
            msg="Error during S3 URL lookup",
            extra={
                "ingest_id": str(ingest_id),
                "error_code": err.response.get("Error", {}).get("Code"),
                "error_message": str(err),
            },
        )

    return None
