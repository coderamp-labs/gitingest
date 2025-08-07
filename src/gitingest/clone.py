"""Module containing functions for cloning a Git repository to a local path."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from git import Repo
from gitingest.config import DEFAULT_TIMEOUT
from gitingest.utils.git_utils import (
    check_repo_exists,
    checkout_partial_clone,
    create_git_auth_header,
    create_git_command_with_auth,
    ensure_git_installed,
    is_github_host,
    resolve_commit,
)
from gitingest.utils.logging_config import get_logger
from gitingest.utils.os_utils import ensure_directory_exists_or_create
from gitingest.utils.timeout_wrapper import async_timeout

if TYPE_CHECKING:
    from gitingest.schemas import CloneConfig

# Initialize logger for this module
logger = get_logger(__name__)


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

    logger.info(
        "Starting git clone operation",
        extra={
            "url": url,
            "local_path": local_path,
            "partial_clone": partial_clone,
            "subpath": config.subpath,
            "branch": config.branch,
            "tag": config.tag,
            "commit": config.commit,
            "include_submodules": config.include_submodules,
        },
    )

    logger.debug("Ensuring git is installed")
    await ensure_git_installed()

    logger.debug("Creating local directory", extra={"parent_path": str(Path(local_path).parent)})
    await ensure_directory_exists_or_create(Path(local_path).parent)

    logger.debug("Checking if repository exists", extra={"url": url})
    if not await check_repo_exists(url, token=token):
        logger.error("Repository not found", extra={"url": url})
        msg = "Repository not found. Make sure it is public or that you have provided a valid token."
        raise ValueError(msg)

    logger.debug("Resolving commit reference")
    commit = await resolve_commit(config, token=token)
    logger.debug("Resolved commit", extra={"commit": commit})

    def perform_clone():
        """Perform the git clone operation using GitPython."""
        try:
            # Set up clone options
            clone_kwargs = {
                "single_branch": True,
                "depth": 1,
                "no_checkout": True,
            }

            # Add authentication for GitHub repositories
            env = None
            if token and is_github_host(url):
                import os
                env = os.environ.copy()
                env["GIT_CONFIG_PARAMETERS"] = create_git_auth_header(token, url=url)

            # Add filter and sparse options for partial clones
            if partial_clone:
                clone_kwargs["multi_options"] = ["--filter=blob:none", "--sparse"]

            # Clone the repository
            logger.info("Executing git clone command")
            repo = Repo.clone_from(url, local_path, env=env, **clone_kwargs)
            logger.info("Git clone completed successfully")
            return repo

        except Exception as e:
            raise RuntimeError(f"Failed to clone repository: {str(e)}") from e

    # Perform the clone operation
    repo = await asyncio.get_event_loop().run_in_executor(None, perform_clone)

    # Checkout the subpath if it is a partial clone
    if partial_clone:
        logger.info("Setting up partial clone for subpath", extra={"subpath": config.subpath})
        await checkout_partial_clone(config, token=token)
        logger.debug("Partial clone setup completed")

    def perform_checkout():
        """Perform the checkout operations using GitPython."""
        try:
            # Fetch the specific commit
            logger.debug("Fetching specific commit", extra={"commit": commit})
            
            # Set up authentication for fetch operations
            if token and is_github_host(url):
                git_cmd = repo.git.with_custom_environment(GIT_CONFIG_PARAMETERS=create_git_auth_header(token, url=url))
            else:
                git_cmd = repo.git

            git_cmd.fetch("--depth=1", "origin", commit)

            # Checkout the specific commit
            logger.info("Checking out commit", extra={"commit": commit})
            repo.git.checkout(commit)

            # Update submodules if requested
            if config.include_submodules:
                logger.info("Updating submodules")
                repo.git.submodule("update", "--init", "--recursive", "--depth=1")
                logger.debug("Submodules updated successfully")

        except Exception as e:
            raise RuntimeError(f"Failed during checkout operations: {str(e)}") from e

    # Perform checkout operations
    await asyncio.get_event_loop().run_in_executor(None, perform_checkout)

    logger.info("Git clone operation completed successfully", extra={"local_path": local_path})
