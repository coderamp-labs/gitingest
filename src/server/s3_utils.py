"""S3 utility functions for uploading and managing digest files."""

from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from uuid import UUID  # noqa: TC003 (typing-only-standard-library-import) needed for type checking (pydantic)

import boto3
from botocore.exceptions import ClientError
from prometheus_client import Counter

from gitingest.utils.logging_config import get_logger
from server.models import S3Metadata

if TYPE_CHECKING:
    from botocore.client import BaseClient


# Initialize logger for this module
logger = get_logger(__name__)

_s3_ingest_lookup_counter = Counter("gitingest_s3_ingest_lookup", "Number of S3 ingest file lookups")
_s3_ingest_hit_counter = Counter("gitingest_s3_ingest_hit", "Number of S3 ingest file cache hits")
_s3_ingest_miss_counter = Counter("gitingest_s3_ingest_miss", "Number of S3 ingest file cache misses")


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
    subpath: str,
    include_patterns: set[str] | None,
    ignore_patterns: set[str],
) -> str:
    """Generate S3 file path with proper naming convention.

    The file path is formatted as:
    [<S3_DIRECTORY_PREFIX>/]ingest/<provider>/<repo-owner>/<repo-name>/<branch>/<commit-ID>/
    <exclude&include hash>/<owner>-<repo-name>-<subpath-hash>.txt

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
    subpath : str
        Subpath of the repository.
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

    # Create hash of exclude/include patterns for uniqueness
    patterns_str = f"include:{sorted(include_patterns) if include_patterns else []}"
    patterns_str += f"exclude:{sorted(ignore_patterns)}"
    patterns_hash = hashlib.sha256(patterns_str.encode()).hexdigest()[:16]
    subpath_hash = hashlib.sha256(subpath.encode()).hexdigest()[:16]

    file_name = f"{user_name}-{repo_name}-{subpath_hash}.txt"
    base_path = f"ingest/{hostname}/{user_name}/{repo_name}/{commit}/{patterns_hash}/{file_name}"

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
        "Creating S3 client",
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
    logger.info("Starting S3 upload", extra=extra_fields)

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
    logger.info(
        "S3 upload completed successfully",
        extra={
            "bucket_name": bucket_name,
            "s3_file_path": s3_file_path,
            "ingest_id": str(ingest_id),
            "public_url": public_url,
        },
    )

    return public_url


def upload_metadata_to_s3(metadata: S3Metadata, s3_file_path: str, ingest_id: UUID) -> str:
    """Upload metadata JSON to S3 alongside the digest file.

    Parameters
    ----------
    metadata : S3Metadata
        The metadata struct containing summary, tree, and content.
    s3_file_path : str
        The S3 file path for the digest (metadata will use .json extension).
    ingest_id : UUID
        The ingest ID to store as an S3 object tag.

    Returns
    -------
    str
        Public URL to access the uploaded metadata file.

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

    # Generate metadata file path by replacing .txt with .json
    metadata_file_path = s3_file_path.replace(".txt", ".json")

    s3_client = create_s3_client()
    bucket_name = get_s3_bucket_name()

    extra_fields = {
        "bucket_name": bucket_name,
        "metadata_file_path": metadata_file_path,
        "ingest_id": str(ingest_id),
        "metadata_size": len(metadata.model_dump_json()),
    }

    # Log upload attempt
    logger.info("Starting S3 metadata upload", extra=extra_fields)

    try:
        # Upload the metadata with ingest_id as tag
        s3_client.put_object(
            Bucket=bucket_name,
            Key=metadata_file_path,
            Body=metadata.model_dump_json(indent=2).encode("utf-8"),
            ContentType="application/json",
            Tagging=f"ingest_id={ingest_id!s}",
        )
    except ClientError as err:
        # Log upload failure
        logger.exception(
            "S3 metadata upload failed",
            extra={
                "bucket_name": bucket_name,
                "metadata_file_path": metadata_file_path,
                "ingest_id": str(ingest_id),
                "error_code": err.response.get("Error", {}).get("Code"),
                "error_message": str(err),
            },
        )
        msg = f"Failed to upload metadata to S3: {err}"
        raise S3UploadError(msg) from err

    # Generate public URL
    alias_host = get_s3_alias_host()
    if alias_host:
        # Use alias host if configured
        public_url = f"{alias_host.rstrip('/')}/{metadata_file_path}"
    else:
        # Fallback to direct S3 URL
        endpoint = get_s3_config().get("endpoint_url")
        if endpoint:
            public_url = f"{endpoint.rstrip('/')}/{bucket_name}/{metadata_file_path}"
        else:
            public_url = (
                f"https://{bucket_name}.s3.{get_s3_config()['region_name']}.amazonaws.com/{metadata_file_path}"
            )

    # Log successful upload
    logger.info(
        "S3 metadata upload completed successfully",
        extra={
            "bucket_name": bucket_name,
            "metadata_file_path": metadata_file_path,
            "ingest_id": str(ingest_id),
            "public_url": public_url,
        },
    )

    return public_url


def get_metadata_from_s3(s3_file_path: str) -> S3Metadata | None:
    """Retrieve metadata JSON from S3.

    Parameters
    ----------
    s3_file_path : str
        The S3 file path for the digest (metadata will use .json extension).

    Returns
    -------
    S3Metadata | None
        The metadata struct if found, None otherwise.

    """
    if not is_s3_enabled():
        return None

    # Generate metadata file path by replacing .txt with .json
    metadata_file_path = s3_file_path.replace(".txt", ".json")

    try:
        s3_client = create_s3_client()
        bucket_name = get_s3_bucket_name()

        # Get the metadata object
        response = s3_client.get_object(Bucket=bucket_name, Key=metadata_file_path)
        metadata_content = response["Body"].read().decode("utf-8")

        return S3Metadata.model_validate_json(metadata_content)
    except ClientError as err:
        # Object doesn't exist if we get a 404 error
        error_code = err.response.get("Error", {}).get("Code")
        if error_code == "404":
            logger.info("Metadata file not found", extra={"metadata_file_path": metadata_file_path})
            return None
        # Log other errors but don't fail
        logger.warning("Failed to retrieve metadata from S3", extra={"error": str(err)})
        return None
    except Exception as exc:
        # For any other exception, log and return None
        logger.warning("Unexpected error retrieving metadata from S3", extra={"error": str(exc)})
        return None


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


def check_s3_object_exists(s3_file_path: str) -> bool:
    """Check if an S3 object exists at the given path.

    Parameters
    ----------
    s3_file_path : str
        The S3 file path to check.

    Returns
    -------
    bool
        True if the object exists, False otherwise.

    Raises
    ------
    ClientError
        If there's an S3 error other than 404 (not found).

    """
    if not is_s3_enabled():
        logger.info("S3 not enabled, skipping object existence check", extra={"s3_file_path": s3_file_path})
        return False

    logger.info("Checking S3 object existence", extra={"s3_file_path": s3_file_path})
    _s3_ingest_lookup_counter.inc()
    try:
        s3_client = create_s3_client()
        bucket_name = get_s3_bucket_name()

        # Use head_object to check if the object exists without downloading it
        s3_client.head_object(Bucket=bucket_name, Key=s3_file_path)
    except ClientError as err:
        # Object doesn't exist if we get a 404 error
        error_code = err.response.get("Error", {}).get("Code")
        if error_code == "404":
            logger.info(
                "S3 object not found",
                extra={
                    "s3_file_path": s3_file_path,
                    "bucket_name": get_s3_bucket_name(),
                    "error_code": error_code,
                },
            )
            _s3_ingest_miss_counter.inc()
            return False
        # Re-raise other errors (permissions, etc.)
        raise
    except Exception as exc:
        # For any other exception, assume object doesn't exist
        logger.info(
            "S3 object check failed with exception, assuming not found",
            extra={
                "s3_file_path": s3_file_path,
                "bucket_name": get_s3_bucket_name(),
                "exception": str(exc),
            },
        )
        _s3_ingest_miss_counter.inc()
        return False
    else:
        logger.info(
            "S3 object found",
            extra={
                "s3_file_path": s3_file_path,
                "bucket_name": get_s3_bucket_name(),
            },
        )
        _s3_ingest_hit_counter.inc()
        return True


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
        logger.debug("S3 not enabled, skipping URL lookup", extra={"ingest_id": str(ingest_id)})
        return None

    logger.info("Starting S3 URL lookup for ingest ID", extra={"ingest_id": str(ingest_id)})

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
                    logger.info(
                        "Found S3 object for ingest ID",
                        extra={
                            "ingest_id": str(ingest_id),
                            "s3_key": key,
                            "s3_url": s3_url,
                            "objects_checked": objects_checked,
                        },
                    )
                    return s3_url

        logger.info(
            "No S3 object found for ingest ID",
            extra={
                "ingest_id": str(ingest_id),
                "objects_checked": objects_checked,
            },
        )

    except ClientError as err:
        logger.exception(
            "Error during S3 URL lookup",
            extra={
                "ingest_id": str(ingest_id),
                "error_code": err.response.get("Error", {}).get("Code"),
                "error_message": str(err),
            },
        )

    return None
