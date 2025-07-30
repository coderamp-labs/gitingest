"""Pydantic models for the query form."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Union

from pydantic import BaseModel, Field, field_validator

from gitingest.utils.compat_func import removesuffix
from server.server_config import MAX_FILE_SIZE_KB

# needed for type checking (pydantic)
if TYPE_CHECKING:
    from server.form_types import IntForm, OptStrForm, StrForm


class PatternType(str, Enum):
    """Enumeration for pattern types used in file filtering."""

    INCLUDE = "include"
    EXCLUDE = "exclude"


class IngestRequest(BaseModel):
    """Request model for the /api/ingest endpoint.

    Attributes
    ----------
    input_text : str
        The Git repository URL or slug to ingest.
    max_file_size : int
        Maximum file size slider position (0-500) for filtering files.
    pattern_type : PatternType
        Type of pattern to use for file filtering (include or exclude).
    pattern : str
        Glob/regex pattern string for file filtering.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    """

    input_text: str = Field(..., description="Git repository URL or slug to ingest")
    max_file_size: int = Field(..., ge=1, le=MAX_FILE_SIZE_KB, description="File size in KB")
    pattern_type: PatternType = Field(default=PatternType.EXCLUDE, description="Pattern type for file filtering")
    pattern: str = Field(default="", description="Glob/regex pattern for file filtering")
    token: str | None = Field(default=None, description="GitHub PAT for private repositories")

    @field_validator("input_text")
    @classmethod
    def validate_input_text(cls, v: str) -> str:
        """Validate that ``input_text`` is not empty."""
        if not v.strip():
            err = "input_text cannot be empty"
            raise ValueError(err)
        return removesuffix(v.strip(), ".git")

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: str) -> str:
        """Validate ``pattern`` field."""
        return v.strip()


class IngestSuccessResponse(BaseModel):
    """Success response model for the /api/ingest endpoint.

    Attributes
    ----------
    repo_url : str
        The original repository URL that was processed.
    short_repo_url : str
        Short form of repository URL (user/repo).
    summary : str
        Summary of the ingestion process including token estimates.
    digest_url : str
        URL to download the full digest content (either S3 URL or local download endpoint).
    tree : str
        File tree structure of the repository.
    content : str
        Processed content from the repository files.
    default_max_file_size : int
        The file size slider position used.
    pattern_type : str
        The pattern type used for filtering.
    pattern : str
        The pattern used for filtering.

    """

    repo_url: str = Field(..., description="Original repository URL")
    short_repo_url: str = Field(..., description="Short repository URL (user/repo)")
    summary: str = Field(..., description="Ingestion summary with token estimates")
    digest_url: str = Field(..., description="URL to download the full digest content")
    tree: str = Field(..., description="File tree structure")
    content: str = Field(..., description="Processed file content")
    default_max_file_size: int = Field(..., description="File size slider position used")
    pattern_type: str = Field(..., description="Pattern type used")
    pattern: str = Field(..., description="Pattern used")


class IngestErrorResponse(BaseModel):
    """Error response model for the /api/ingest endpoint.

    Attributes
    ----------
    error : str
        Error message describing what went wrong.

    """

    error: str = Field(..., description="Error message")


# Union type for API responses
IngestResponse = Union[IngestSuccessResponse, IngestErrorResponse]


class S3Metadata(BaseModel):
    """Model for S3 metadata structure.

    Attributes
    ----------
    summary : str
        Summary of the ingestion process including token estimates.
    tree : str
        File tree structure of the repository.
    content : str
        Processed content from the repository files.

    """

    summary: str = Field(..., description="Ingestion summary with token estimates")
    tree: str = Field(..., description="File tree structure")
    content: str = Field(..., description="Processed file content")


class QueryForm(BaseModel):
    """Form data for the query.

    Attributes
    ----------
    input_text : str
        Text or URL supplied in the form.
    max_file_size : int
        The maximum allowed file size for the input, specified by the user.
    pattern_type : str
        The type of pattern used for the query (``include`` or ``exclude``).
    pattern : str
        Glob/regex pattern string.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    """

    input_text: str
    max_file_size: int
    pattern_type: str
    pattern: str
    token: str | None = None

    @classmethod
    def as_form(
        cls,
        input_text: StrForm,
        max_file_size: IntForm,
        pattern_type: StrForm,
        pattern: StrForm,
        token: OptStrForm,
    ) -> QueryForm:
        """Create a QueryForm from FastAPI form parameters.

        Parameters
        ----------
        input_text : StrForm
            The input text provided by the user.
        max_file_size : IntForm
            The maximum allowed file size for the input.
        pattern_type : StrForm
            The type of pattern used for the query (``include`` or ``exclude``).
        pattern : StrForm
            Glob/regex pattern string.
        token : OptStrForm
            GitHub personal access token (PAT) for accessing private repositories.

        Returns
        -------
        QueryForm
            The QueryForm instance.

        """
        return cls(
            input_text=input_text,
            max_file_size=max_file_size,
            pattern_type=pattern_type,
            pattern=pattern,
            token=token,
        )
