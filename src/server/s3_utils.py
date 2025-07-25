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
    s3_enabled = os.getenv("S3_ENABLED", "false").lower() == "true"
    logger.info(f"S3 enabled check: S3_ENABLED={os.getenv('S3_ENABLED', 'false')}, result={s3_enabled}")
    return s3_enabled

def get_s3_config() -> dict[str, str | None]:
    """Get S3 configuration from environment variables."""
    config = {
        "endpoint_url": os.getenv("S3_ENDPOINT"),
        "aws_access_key_id": os.getenv("S3_ACCESS_KEY"),
        "aws_secret_access_key": os.getenv("S3_SECRET_KEY"),
        "region_name": os.getenv("S3_REGION") or os.getenv("AWS_REGION", "us-east-1"),
    }
    
    # Log config validation (without sensitive data)
    config_status = {
        "endpoint_url": "SET" if config["endpoint_url"] else "NOT_SET",
        "aws_access_key_id": "SET" if config["aws_access_key_id"] else "NOT_SET", 
        "aws_secret_access_key": "SET" if config["aws_secret_access_key"] else "NOT_SET",
        "region_name": config["region_name"]
    }
    logger.info(f"S3 config status: {config_status}")
    
    filtered_config = {k: v for k, v in config.items() if v is not None}
    logger.info(f"S3 config keys present: {list(filtered_config.keys())}")
    
    return filtered_config


def get_s3_bucket_name() -> str:
    """Get S3 bucket name from environment variables."""
    bucket_name = os.getenv("S3_BUCKET_NAME", "gitingest-bucket")
    logger.info(f"S3 bucket name: {bucket_name}")
    return bucket_name


def get_s3_alias_host() -> str | None:
    """Get S3 alias host for public URLs."""
    alias_host = os.getenv("S3_ALIAS_HOST")
    logger.info(f"S3 alias host: {'SET' if alias_host else 'NOT_SET'}")
    return alias_host


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
    try:
        config = get_s3_config()
        
        # Log S3 client creation (excluding sensitive info)
        log_config = config.copy()
        has_access_key = bool(log_config.pop("aws_access_key_id", None))
        has_secret_key = bool(log_config.pop("aws_secret_access_key", None))
        
        logger.info(
            f"Creating S3 client - endpoint: {log_config.get('endpoint_url', 'NOT_SET')}, "
            f"region: {log_config.get('region_name', 'NOT_SET')}, "
            f"has_access_key: {has_access_key}, has_secret_key: {has_secret_key}, "
            f"credentials_provided: {has_access_key and has_secret_key}"
        )
        
        client = boto3.client("s3", **config)
        
        # Test client by attempting to list buckets (this will fail if credentials are wrong)
        try:
            # This is a lightweight test of the client credentials
            client.list_buckets()
            logger.info("S3 client created successfully and credentials validated")
        except ClientError as test_err:
            logger.warning(
                f"S3 client created but credential validation failed - "
                f"error_code: {test_err.response.get('Error', {}).get('Code')}, "
                f"error_message: {str(test_err)}"
            )
        
        return client
        
    except Exception as err:
        logger.error(
            f"Failed to create S3 client - error_type: {type(err).__name__}, "
            f"error_message: {str(err)}"
        )
        raise


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

    # Log upload attempt
    logger.info(f"Starting S3 upload - ingest_id: {ingest_id}, EXACT_UPLOAD: s3://{bucket_name}/{s3_file_path}, content_size: {len(content)}")

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
        logger.error(
            f"S3 upload failed - bucket: {bucket_name}, path: {s3_file_path}, ingest_id: {ingest_id}, "
            f"error_code: {err.response.get('Error', {}).get('Code')}, error_message: {str(err)}"
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
    logger.info(f"S3 upload completed successfully - bucket: {bucket_name}, path: {s3_file_path}, ingest_id: {ingest_id}, public_url: {public_url}")

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
        logger.info(f"Checking tags for S3 object: {key}, target_ingest_id: {target_ingest_id}")
        
        tags_response = s3_client.get_object_tagging(Bucket=bucket_name, Key=key)
        tags = {tag["Key"]: tag["Value"] for tag in tags_response.get("TagSet", [])}
        
        logger.info(f"S3 object tags retrieved - key: {key}, target_ingest_id: {target_ingest_id}, tags: {tags}")
        
        match_found = tags.get("ingest_id") == str(target_ingest_id)
        if match_found:
            logger.info(f"Tag match found for {key}, target_ingest_id: {target_ingest_id}")
        
        return match_found
        
    except ClientError as err:
        logger.warning(
            f"Failed to get object tags - key: {key}, target_ingest_id: {target_ingest_id}, "
            f"error_code: {err.response.get('Error', {}).get('Code')}, error_message: {str(err)}"
        )
        return False
    except Exception as err:
        logger.warning(
            f"Unexpected error checking object tags - key: {key}, target_ingest_id: {target_ingest_id}, "
            f"error_type: {type(err).__name__}, error_message: {str(err)}"
        )
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
        logger.info(f"S3 not enabled, skipping URL lookup for ingest_id: {ingest_id}")
        return None

    logger.info(f"Starting S3 URL lookup for ingest_id: {ingest_id}")

    try:
        s3_client = create_s3_client()
        bucket_name = get_s3_bucket_name()
        
        logger.info(f"S3 lookup initialized - ingest_id: {ingest_id}, bucket_name: {bucket_name}")

        # List all objects in the ingest/ prefix and check their tags
        # Include S3_DIRECTORY_PREFIX if set
        search_prefix = "ingest/"
        s3_directory_prefix = os.getenv("S3_DIRECTORY_PREFIX")
        if s3_directory_prefix:
            search_prefix = f"{s3_directory_prefix.rstrip('/')}/ingest/"
            logger.info(f"Using S3 directory prefix for search - ingest_id: {ingest_id}, directory_prefix: {s3_directory_prefix}")
        else:
            logger.info(f"No S3 directory prefix set, using default search - ingest_id: {ingest_id}")
        
        try:
            paginator = s3_client.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=search_prefix)
            
            logger.info(f"S3 paginator created, starting object scan - ingest_id: {ingest_id}, EXACT_SEARCH: s3://{bucket_name}/{search_prefix}")
        except ClientError as paginator_err:
            logger.error(
                f"Failed to create S3 paginator - ingest_id: {ingest_id}, bucket_name: {bucket_name}, "
                f"error_code: {paginator_err.response.get('Error', {}).get('Code')}, error_message: {str(paginator_err)}"
            )
            return None

        objects_checked = 0
        pages_processed = 0
        
        for page in page_iterator:
            pages_processed += 1
            logger.info(f"Processing S3 page {pages_processed} - ingest_id: {ingest_id}")
            
            if "Contents" not in page:
                logger.info(f"S3 page {pages_processed} has no contents - ingest_id: {ingest_id}")
                continue

            for obj in page["Contents"]:
                key = obj["Key"]
                objects_checked += 1
                
                logger.info(f"Checking S3 object {objects_checked}: {key} - ingest_id: {ingest_id}")
                
                if _check_object_tags(
                    s3_client=s3_client,
                    bucket_name=bucket_name,
                    key=key,
                    target_ingest_id=ingest_id,
                ):
                    s3_url = _build_s3_url(key)
                    logger.info(
                        f"Found matching S3 object for ingest ID - ingest_id: {ingest_id}, s3_key: {key}, "
                        f"s3_url: {s3_url}, objects_checked: {objects_checked}, pages_processed: {pages_processed}"
                    )
                    return s3_url

        logger.info(
            f"No matching S3 object found for ingest ID - ingest_id: {ingest_id}, objects_checked: {objects_checked}, "
            f"pages_processed: {pages_processed}, bucket_name: {bucket_name}"
        )

    except ClientError as err:
        logger.error(
            f"S3 client error during URL lookup - ingest_id: {ingest_id}, "
            f"error_code: {err.response.get('Error', {}).get('Code')}, error_message: {str(err)}, "
            f"bucket_name: {get_s3_bucket_name()}"
        )
    except Exception as err:
        logger.error(
            f"Unexpected error during S3 URL lookup - ingest_id: {ingest_id}, "
            f"error_type: {type(err).__name__}, error_message: {str(err)}"
        )

    return None
