"""Module containing functions for cloning a Git repository to a local path."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from gitingest.config import DEFAULT_TIMEOUT
from gitingest.utils.git_utils import (
    check_repo_exists,
    checkout_partial_clone,
    create_git_auth_header,
    create_git_command,
    ensure_git_installed,
    is_github_host,
    resolve_commit,
    run_command,
)
from gitingest.utils.os_utils import ensure_directory_exists_or_create
from gitingest.utils.timeout_wrapper import async_timeout

if TYPE_CHECKING:
    from gitingest.schemas import CloneConfig


@async_timeout(DEFAULT_TIMEOUT)
async def clone_repo(config: CloneConfig, *, token: str | None = None) -> None:
    """Clone a repository to a local path based on the provided configuration.

    This function handles the process of cloning a Git repository to the local file system.
    It can clone a specific branch, tag, or commit if provided, and it raises exceptions if
    any errors occur during the cloning process.

    Parameters
    ----------
    config : CloneConfig
        The configuration for cloning the repository.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Raises
    ------
    ValueError
        If the repository is not found, if the provided URL is invalid, or if the token format is invalid.

    """
    # Extract and validate query parameters
    url: str = config.url
    local_path: str = config.local_path
    partial_clone: bool = config.subpath != "/"

    await ensure_git_installed()
    await ensure_directory_exists_or_create(Path(local_path).parent)

    if not await check_repo_exists(url, token=token):
        msg = "Repository not found. Make sure it is public or that you have provided a valid token."
        raise ValueError(msg)

    commit = await resolve_commit(config, token=token)

    clone_cmd = ["git"]
    if token and is_github_host(url):
        clone_cmd += ["-c", create_git_auth_header(token, url=url)]

    clone_cmd += ["clone", "--single-branch", "--no-checkout", "--depth=1"]
    if partial_clone:
        clone_cmd += ["--filter=blob:none", "--sparse"]

    clone_cmd += [url, local_path]

    # Clone the repository
    await run_command(*clone_cmd)

    # Checkout the subpath if it is a partial clone
    if partial_clone:
        await checkout_partial_clone(config, token=token)

    git = create_git_command(["git"], local_path, url, token)

    # Ensure the commit is locally available
    await run_command(*git, "fetch", "--depth=1", "origin", commit)

    # Write the work-tree at that commit
    await run_command(*git, "checkout", commit)

    # Update submodules
    if config.include_submodules:
        await run_command(*git, "submodule", "update", "--init", "--recursive", "--depth=1")
