"""Module containing the dataclasses for the ingestion process."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 (typing-only-standard-library-import) needed for type checking (pydantic)
from uuid import UUID  # noqa: TC003 (typing-only-standard-library-import) needed for type checking (pydantic)

from pydantic import BaseModel, Field

from gitingest.config import MAX_DIRECTORY_DEPTH, MAX_FILES, MAX_FILE_SIZE, MAX_TOTAL_SIZE_BYTES
from gitingest.schemas.cloning import CloneConfig


class IngestionQuery(BaseModel):  # pylint: disable=too-many-instance-attributes
    """Pydantic model to store the parsed details of the repository or file path.

    Attributes
    ----------
    host : str | None
        The host of the repository.
    user_name : str | None
        Username or owner of the repository.
    repo_name : str | None
        Name of the repository.
    local_path : Path
        Local path to the repository or file.
    url : str | None
        URL of the repository.
    slug : str
        The slug of the repository.
    id : UUID
        The ID of the repository.
    subpath : str
        Subpath to the repository or file (default: ``"/"``).
    type : str | None
        Type of the repository or file.
    branch : str | None
        Branch of the repository.
    commit : str | None
        Commit of the repository.
    tag: str | None
        Tag of the repository.
    max_file_size : int
        Maximum file size in bytes to ingest (default: 10 MB).
    max_files : int
        Maximum number of files to ingest (default: 10,000).
    max_total_size_bytes : int
        Maximum total size of output file in bytes (default: 500 MB).
    max_directory_depth : int
        Maximum depth of directory traversal (default: 20).
    ignore_patterns : set[str]
        Patterns to ignore.
    include_patterns : set[str] | None
        Patterns to include.
    include_submodules : bool
        Whether to include all Git submodules within the repository. (default: ``False``)
    s3_url : str | None
        The S3 URL where the digest is stored if S3 is enabled.

    """

    host: str | None = None
    user_name: str | None = None
    repo_name: str | None = None
    local_path: Path
    url: str | None = None
    slug: str
    id: UUID
    subpath: str = Field(default="/")
    type: str | None = None
    branch: str | None = None
    commit: str | None = None
    tag: str | None = None
    max_file_size: int = Field(default=MAX_FILE_SIZE)
    max_files: int = Field(default=MAX_FILES)
    max_total_size_bytes: int = Field(default=MAX_TOTAL_SIZE_BYTES)
    max_directory_depth: int = Field(default=MAX_DIRECTORY_DEPTH)
    ignore_patterns: set[str] = Field(default_factory=set)  # TODO: ssame type for ignore_* and include_* patterns
    include_patterns: set[str] | None = None
    include_submodules: bool = Field(default=False)
    s3_url: str | None = None

    def extract_clone_config(self) -> CloneConfig:
        """Extract the relevant fields for the CloneConfig object.

        Returns
        -------
        CloneConfig
            A CloneConfig object containing the relevant fields.

        Raises
        ------
        ValueError
            If the ``url`` parameter is not provided.

        """
        if not self.url:
            msg = "The 'url' parameter is required."
            raise ValueError(msg)

        return CloneConfig(
            url=self.url,
            local_path=str(self.local_path),
            commit=self.commit,
            branch=self.branch,
            tag=self.tag,
            subpath=self.subpath,
            blob=self.type == "blob",
            include_submodules=self.include_submodules,
        )
