"""Module containing the dataclasses for the ingestion process."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 (typing-only-standard-library-import) needed for type checking (pydantic)

from pydantic import BaseModel, Field

from gitingest.config import MAX_FILE_SIZE


class CloneConfig(BaseModel):  # pylint: disable=too-many-instance-attributes
    """Configuration for cloning a Git repository.

    This model holds the necessary parameters for cloning a repository to a local path, including
    the repository's URL, the target local path, and optional parameters for a specific commit, branch, or tag.

    Attributes
    ----------
    url : str
        The URL of the Git repository to clone.
    local_path : str
        The local directory where the repository will be cloned.
    commit : str | None
        The specific commit hash to check out after cloning.
    branch : str | None
        The branch to clone.
    tag : str | None
        The tag to clone.
    subpath : str
        The subpath to clone from the repository (default: ``"/"``).
    blob : bool
        Whether the repository is a blob (default: ``False``).
    include_submodules : bool
        Whether to clone submodules (default: ``False``).

    """

    url: str
    local_path: str
    commit: str | None = None
    branch: str | None = None
    tag: str | None = None
    subpath: str = Field(default="/")
    blob: bool = Field(default=False)
    include_submodules: bool = Field(default=False)


class IngestionQuery(BaseModel):  # pylint: disable=too-many-instance-attributes
    """Pydantic model to store the parsed details of the repository or file path.

    Attributes
    ----------
    host : str | None
        The host of the repository.
    user_name : str | None
        The username or owner of the repository.
    repo_name : str | None
        The name of the repository.
    local_path : Path
        The local path to the repository or file.
    url : str | None
        The URL of the repository.
    slug : str
        The slug of the repository.
    id : str
        The ID of the repository.
    subpath : str
        The subpath to the repository or file (default: ``"/"``).
    type : str | None
        The type of the repository or file.
    branch : str | None
        The branch of the repository.
    commit : str | None
        The commit of the repository.
    tag : str | None
        The tag of the repository.
    max_file_size : int
        The maximum file size to ingest (default: 10 MB).
    ignore_patterns : set[str]
        The patterns to ignore (default: ``set()``).
    include_patterns : set[str] | None
        The patterns to include.
    include_submodules : bool
        Whether to include all Git submodules within the repository. (default: ``False``)

    """

    host: str | None = None
    user_name: str | None = None
    repo_name: str | None = None
    local_path: Path
    url: str | None = None
    slug: str
    id: str
    subpath: str = Field(default="/")
    type: str | None = None
    branch: str | None = None
    commit: str | None = None
    tag: str | None = None
    max_file_size: int = Field(default=MAX_FILE_SIZE)
    ignore_patterns: set[str] = Field(default_factory=set)  # TODO: ssame type for ignore_* and include_* patterns
    include_patterns: set[str] | None = None
    include_submodules: bool = Field(default=False)

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
