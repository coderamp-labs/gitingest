"""Ingest endpoint for the API."""

import logging
from typing import Union
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from prometheus_client import Counter

from gitingest.config import TMP_BASE_PATH
from server.models import IngestRequest
from server.routers_utils import COMMON_INGEST_RESPONSES, _perform_ingestion
from server.s3_utils import get_s3_url_for_ingest_id, is_s3_enabled
from server.server_config import MAX_DISPLAY_SIZE
from server.server_utils import limiter

ingest_counter = Counter("gitingest_ingest_total", "Number of ingests", ["status", "url"])

router = APIRouter()

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

@router.post("/api/ingest", responses=COMMON_INGEST_RESPONSES)
@limiter.limit("10/minute")
async def api_ingest(
    request: Request,  # noqa: ARG001 (unused-function-argument) # pylint: disable=unused-argument
    ingest_request: IngestRequest,
) -> JSONResponse:
    """Ingest a Git repository and return processed content.

    **This endpoint processes a Git repository by cloning it, analyzing its structure,**
    and returning a summary with the repository's content. The response includes
    file tree structure, processed content, and metadata about the ingestion.

    **Parameters**

    - **ingest_request** (`IngestRequest`): Pydantic model containing ingestion parameters

    **Returns**

    - **JSONResponse**: Success response with ingestion results or error response with appropriate HTTP status code

    """
    response = await _perform_ingestion(
        input_text=ingest_request.input_text,
        max_file_size=ingest_request.max_file_size,
        pattern_type=ingest_request.pattern_type.value,
        pattern=ingest_request.pattern,
        token=ingest_request.token,
    )
    # limit URL to 255 characters
    ingest_counter.labels(status=response.status_code, url=ingest_request.input_text[:255]).inc()
    return response


@router.get("/api/{user}/{repository}", responses=COMMON_INGEST_RESPONSES)
@limiter.limit("10/minute")
async def api_ingest_get(
    request: Request,  # noqa: ARG001 (unused-function-argument) # pylint: disable=unused-argument
    user: str,
    repository: str,
    max_file_size: int = MAX_DISPLAY_SIZE,
    pattern_type: str = "exclude",
    pattern: str = "",
    token: str = "",
) -> JSONResponse:
    """Ingest a GitHub repository via GET and return processed content.

    **This endpoint processes a GitHub repository by analyzing its structure and returning a summary**
    with the repository's content. The response includes file tree structure, processed content, and
    metadata about the ingestion. All ingestion parameters are optional and can be provided as query parameters.

    **Path Parameters**
    - **user** (`str`): GitHub username or organization
    - **repository** (`str`): GitHub repository name

    **Query Parameters**
    - **max_file_size** (`int`, optional): Maximum file size to include in the digest (default: 50 KB)
    - **pattern_type** (`str`, optional): Type of pattern to use ("include" or "exclude", default: "exclude")
    - **pattern** (`str`, optional): Pattern to include or exclude in the query (default: "")
    - **token** (`str`, optional): GitHub personal access token for private repositories (default: "")

    **Returns**
    - **JSONResponse**: Success response with ingestion results or error response with appropriate HTTP status code
    """
    response = await _perform_ingestion(
        input_text=f"{user}/{repository}",
        max_file_size=max_file_size,
        pattern_type=pattern_type,
        pattern=pattern,
        token=token or None,
    )
    # limit URL to 255 characters
    ingest_counter.labels(status=response.status_code, url=f"{user}/{repository}"[:255]).inc()
    return response



@router.get("/api/download/file/{ingest_id}", response_model=None)
async def download_ingest(
    ingest_id: UUID,
) -> Union[RedirectResponse, FileResponse]:  # noqa: FA100 (future-rewritable-type-annotation) (pydantic)
    """Download the first text file produced for an ingest ID.

    **This endpoint retrieves the first ``*.txt`` file produced during the ingestion process**
    and returns it as a downloadable file. If S3 is enabled and the file is stored in S3,
    it redirects to the S3 URL. Otherwise, it serves the local file.

    **Parameters**

    - **ingest_id** (`UUID`): Identifier that the ingest step emitted

    **Returns**

    - **RedirectResponse**: Redirect to S3 URL if S3 is enabled and file exists in S3
    - **FileResponse**: Streamed response with media type ``text/plain`` for local files

    **Raises**

    - **HTTPException**: **404** - digest directory is missing or contains no ``*.txt`` file
    - **HTTPException**: **403** - the process lacks permission to read the directory or file

    """
    logger = logging.getLogger(__name__)
    
    logger.info("Download request received", extra={
        "ingest_id": str(ingest_id),
        "s3_enabled": is_s3_enabled()
    })
    
    # Check if S3 is enabled and file exists in S3
    if is_s3_enabled():
        logger.info("S3 is enabled, attempting S3 URL lookup", extra={"ingest_id": str(ingest_id)})
        
        try:
            s3_url = get_s3_url_for_ingest_id(ingest_id)
            if s3_url:
                logger.info("File found in S3, redirecting", extra={
                    "ingest_id": str(ingest_id),
                    "s3_url": s3_url,
                    "redirect_status": 302
                })
                return RedirectResponse(url=s3_url, status_code=302)
            else:
                logger.info("File not found in S3, falling back to local file", extra={
                    "ingest_id": str(ingest_id)
                })
        except Exception as s3_err:
            logger.error("Error during S3 URL lookup, falling back to local file", extra={
                "ingest_id": str(ingest_id),
                "error_type": type(s3_err).__name__,
                "error_message": str(s3_err)
            })
    else:
        logger.info("S3 is disabled, serving local file", extra={"ingest_id": str(ingest_id)})

    # Fall back to local file serving
    logger.info("Attempting local file serving", extra={"ingest_id": str(ingest_id)})
    
    # Normalize and validate the directory path
    directory = (TMP_BASE_PATH / str(ingest_id)).resolve()
    
    logger.debug("Local directory path resolved", extra={
        "ingest_id": str(ingest_id),
        "directory_path": str(directory),
        "tmp_base_path": str(TMP_BASE_PATH.resolve())
    })
    
    if not str(directory).startswith(str(TMP_BASE_PATH.resolve())):
        logger.error("Invalid ingest ID - path traversal attempt", extra={
            "ingest_id": str(ingest_id),
            "directory_path": str(directory),
            "tmp_base_path": str(TMP_BASE_PATH.resolve())
        })
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Invalid ingest ID: {ingest_id!r}")

    if not directory.is_dir():
        logger.error("Digest directory not found", extra={
            "ingest_id": str(ingest_id),
            "directory_path": str(directory),
            "directory_exists": directory.exists(),
            "is_directory": directory.is_dir() if directory.exists() else False
        })
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Digest {ingest_id!r} not found")

    try:
        # List all txt files for debugging
        txt_files = list(directory.glob("*.txt"))
        logger.debug("Found txt files in directory", extra={
            "ingest_id": str(ingest_id),
            "directory_path": str(directory),
            "txt_files_count": len(txt_files),
            "txt_files": [f.name for f in txt_files]
        })
        
        first_txt_file = next(directory.glob("*.txt"))
        
        logger.info("Selected txt file for download", extra={
            "ingest_id": str(ingest_id),
            "selected_file": first_txt_file.name,
            "file_path": str(first_txt_file),
            "file_size": first_txt_file.stat().st_size if first_txt_file.exists() else "unknown"
        })
        
    except StopIteration as exc:
        # List all files in directory for debugging
        all_files = list(directory.glob("*"))
        logger.error("No txt file found in digest directory", extra={
            "ingest_id": str(ingest_id),
            "directory_path": str(directory),
            "all_files_count": len(all_files),
            "all_files": [f.name for f in all_files],
            "s3_enabled": is_s3_enabled()
        })
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No .txt file found for digest {ingest_id!r}, s3_enabled: {is_s3_enabled()}"
        ) from exc

    try:
        logger.info("Serving local file", extra={
            "ingest_id": str(ingest_id),
            "file_name": first_txt_file.name,
            "file_path": str(first_txt_file),
            "media_type": "text/plain"
        })
        return FileResponse(path=first_txt_file, media_type="text/plain", filename=first_txt_file.name)
    except PermissionError as exc:
        logger.error("Permission denied accessing file", extra={
            "ingest_id": str(ingest_id),
            "file_path": str(first_txt_file),
            "error_message": str(exc)
        })
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied for {first_txt_file}",
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error serving local file", extra={
            "ingest_id": str(ingest_id),
            "file_path": str(first_txt_file),
            "error_type": type(exc).__name__,
            "error_message": str(exc)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error serving file for digest {ingest_id!r}",
        ) from exc
