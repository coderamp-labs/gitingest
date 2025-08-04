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
    context_size : str
        Desired output size in tokens for the final digest (e.g., "128k", "1M", "500k").
    user_prompt : str
        User prompt to guide AI file selection (optional, uses default if empty).
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    """

    input_text: str = Field(..., description="Git repository URL or slug to ingest")
    context_size: str = Field(default="128k", description="Desired output size in tokens (e.g., '128k', '1M', '500k')")
    user_prompt: str = Field(default="", description="User prompt to guide AI file selection")
    token: str | None = Field(default=None, description="GitHub PAT for private repositories")

    @field_validator("input_text")
    @classmethod
    def validate_input_text(cls, v: str) -> str:
        """Validate that ``input_text`` is not empty."""
        if not v.strip():
            err = "input_text cannot be empty"
            raise ValueError(err)
        return removesuffix(v.strip(), ".git")

    @field_validator("user_prompt")
    @classmethod
    def validate_user_prompt(cls, v: str) -> str:
        """Validate ``user_prompt`` field."""
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
    context_size : str
        The context size used for the digest.
    user_prompt : str
        The user prompt used for AI file selection.
    selected_files : list[str]
        List of file paths selected by AI for inclusion.
    reasoning : str
        AI reasoning for file selection.

    """

    repo_url: str = Field(..., description="Original repository URL")
    short_repo_url: str = Field(..., description="Short repository URL (user/repo)")
    summary: str = Field(..., description="Ingestion summary with token estimates")
    digest_url: str = Field(..., description="URL to download the full digest content")
    tree: str = Field(..., description="File tree structure")
    content: str = Field(..., description="Processed file content")
    context_size: str = Field(..., description="Context size used")
    user_prompt: str = Field(..., description="User prompt used")
    selected_files: list[str] = Field(..., description="AI-selected file paths")
    selected_files_detailed: dict[str, dict] | None = Field(None, description="Detailed file info with reasoning")
    reasoning: str = Field(..., description="AI reasoning for file selection")


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
    context_size : str
        The desired context size for the output.
    user_prompt : str
        User prompt to guide AI file selection.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    """

    input_text: str
    context_size: str
    user_prompt: str
    token: str | None = None

    @classmethod
    def as_form(
        cls,
        input_text: StrForm,
        context_size: StrForm,
        user_prompt: StrForm,
        token: OptStrForm,
    ) -> QueryForm:
        """Create a QueryForm from FastAPI form parameters.

        Parameters
        ----------
        input_text : StrForm
            The input text provided by the user.
        context_size : StrForm
            The desired context size for the output.
        user_prompt : StrForm
            User prompt to guide AI file selection.
        token : OptStrForm
            GitHub personal access token (PAT) for accessing private repositories.

        Returns
        -------
        QueryForm
            The QueryForm instance.

        """
        return cls(
            input_text=input_text,
            context_size=context_size,
            user_prompt=user_prompt,
            token=token,
        )
