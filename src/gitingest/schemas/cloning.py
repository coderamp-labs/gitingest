"""Schema for the cloning process."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
