"""Utility functions for interacting with Git repositories."""

from __future__ import annotations

import asyncio
import base64
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Final, Generator, Iterable
from urllib.parse import urlparse, urlunparse

import git

from gitingest.utils.compat_func import removesuffix
from gitingest.utils.exceptions import InvalidGitHubTokenError
from gitingest.utils.logging_config import get_logger

if TYPE_CHECKING:
    from gitingest.schemas import CloneConfig

# Initialize logger for this module
logger = get_logger(__name__)

# GitHub Personal-Access tokens (classic + fine-grained).
#   - ghp_ / gho_ / ghu_ / ghs_ / ghr_  → 36 alphanumerics
#   - github_pat_                       → 22 alphanumerics + "_" + 59 alphanumerics
_GITHUB_PAT_PATTERN: Final[str] = r"^(?:gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59})$"


def is_github_host(url: str) -> bool:
    """Check if a URL is from a GitHub host (github.com or GitHub Enterprise).

    Parameters
    ----------
    url : str
        The URL to check

    Returns
    -------
    bool
        True if the URL is from a GitHub host, False otherwise

    """
    hostname = urlparse(url).hostname or ""
    return hostname.startswith("github.")


async def run_command(*args: str) -> tuple[bytes, bytes]:
    """Execute a shell command asynchronously and return (stdout, stderr) bytes.

    This function is kept for backward compatibility with non-git commands.
    Git operations should use GitPython directly.

    Parameters
    ----------
    *args : str
        The command and its arguments to execute.

    Returns
    -------
    tuple[bytes, bytes]
        A tuple containing the stdout and stderr of the command.

    Raises
    ------
    RuntimeError
        If command exits with a non-zero status.

    """
    # Execute the requested command
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        msg = f"Command failed: {' '.join(args)}\nError: {stderr.decode().strip()}"
        raise RuntimeError(msg)

    return stdout, stderr


async def ensure_git_installed() -> None:
    """Ensure Git is installed and accessible on the system.

    On Windows, this also checks whether Git is configured to support long file paths.

    Raises
    ------
    RuntimeError
        If Git is not installed or not accessible.

    """
    try:
        # Use GitPython to check git availability
        git_cmd = git.Git()
        git_cmd.version()
    except git.GitCommandError as exc:
        msg = "Git is not installed or not accessible. Please install Git first."
        raise RuntimeError(msg) from exc
    except Exception as exc:
        msg = "Git is not installed or not accessible. Please install Git first."
        raise RuntimeError(msg) from exc

    if sys.platform == "win32":
        try:
            longpaths_value = git_cmd.config("core.longpaths")
            if longpaths_value.lower() != "true":
                logger.warning(
                    "Git clone may fail on Windows due to long file paths. "
                    "Consider enabling long path support with: 'git config --global core.longpaths true'. "
                    "Note: This command may require administrator privileges.",
                    extra={"platform": "windows", "longpaths_enabled": False},
                )
        except git.GitCommandError:
            # Ignore if checking 'core.longpaths' fails.
            pass


async def check_repo_exists(url: str, token: str | None = None) -> bool:
    """Check whether a remote Git repository is reachable.

    Parameters
    ----------
    url : str
        URL of the Git repository to check.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Returns
    -------
    bool
        ``True`` if the repository exists, ``False`` otherwise.

    """
    try:
        # Try to resolve HEAD - if repo exists, this will work
        await _resolve_ref_to_sha(url, "HEAD", token=token)
    except (ValueError, Exception):
        # Repository doesn't exist, is private without proper auth, or other error
        return False

    return True


def _parse_github_url(url: str) -> tuple[str, str, str]:
    """Parse a GitHub URL and return (hostname, owner, repo).

    Parameters
    ----------
    url : str
        The URL of the GitHub repository to parse.

    Returns
    -------
    tuple[str, str, str]
        A tuple containing the hostname, owner, and repository name.

    Raises
    ------
    ValueError
        If the URL is not a valid GitHub repository URL.

    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        msg = f"URL must start with http:// or https://: {url!r}"
        raise ValueError(msg)

    if not parsed.hostname or not parsed.hostname.startswith("github."):
        msg = f"Un-recognised GitHub hostname: {parsed.hostname!r}"
        raise ValueError(msg)

    parts = removesuffix(parsed.path, ".git").strip("/").split("/")
    expected_path_length = 2
    if len(parts) != expected_path_length:
        msg = f"Path must look like /<owner>/<repo>: {parsed.path!r}"
        raise ValueError(msg)

    owner, repo = parts
    return parsed.hostname, owner, repo


async def fetch_remote_branches_or_tags(url: str, *, ref_type: str, token: str | None = None) -> list[str]:
    """Fetch the list of branches or tags from a remote Git repository.

    Parameters
    ----------
    url : str
        The URL of the Git repository to fetch branches or tags from.
    ref_type: str
        The type of reference to fetch. Can be "branches" or "tags".
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Returns
    -------
    list[str]
        A list of branch names available in the remote repository.

    Raises
    ------
    ValueError
        If the ``ref_type`` parameter is not "branches" or "tags".
    RuntimeError
        If fetching branches or tags from the remote repository fails.

    """
    if ref_type not in ("branches", "tags"):
        msg = f"Invalid fetch type: {ref_type}"
        raise ValueError(msg)

    await ensure_git_installed()

    # Use GitPython to get remote references
    try:
        fetch_tags = ref_type == "tags"
        to_fetch = "tags" if fetch_tags else "heads"

        # Build ls-remote command
        cmd_args = [f"--{to_fetch}"]
        if fetch_tags:
            cmd_args.append("--refs")  # Filter out peeled tag objects
        cmd_args.append(url)

        # Run the command with proper authentication
        with git_auth_context(url, token) as (git_cmd, auth_url):
            # Replace the URL in cmd_args with the authenticated URL
            cmd_args[-1] = auth_url  # URL is the last argument
            output = git_cmd.ls_remote(*cmd_args)

        # Parse output
        return [
            line.split(f"refs/{to_fetch}/", 1)[1]
            for line in output.splitlines()
            if line.strip() and f"refs/{to_fetch}/" in line
        ]
    except git.GitCommandError as exc:
        msg = f"Failed to fetch {ref_type} from {url}: {exc}"
        raise RuntimeError(msg) from exc


def create_git_repo(local_path: str, url: str, token: str | None = None) -> git.Repo:
    """Create a GitPython Repo object with authentication if needed.

    Parameters
    ----------
    local_path : str
        The local path where the git repository is located.
    url : str
        The repository URL to check if it's a GitHub repository.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Returns
    -------
    git.Repo
        A GitPython Repo object configured with authentication.

    Raises
    ------
    ValueError
        If the local path is not a valid git repository.

    """
    try:
        repo = git.Repo(local_path)

        # Configure authentication if needed
        if token and is_github_host(url):
            auth_header = create_git_auth_header(token, url=url)
            # Set the auth header in git config for this repo
            key, value = auth_header.split("=", 1)
            repo.git.config(key, value)

    except git.InvalidGitRepositoryError as exc:
        msg = f"Invalid git repository at {local_path}"
        raise ValueError(msg) from exc

    return repo


def create_git_auth_header(token: str, url: str = "https://github.com") -> str:
    """Create a Basic authentication header for GitHub git operations.

    Parameters
    ----------
    token : str
        GitHub personal access token (PAT) for accessing private repositories.
    url : str
        The GitHub URL to create the authentication header for.
        Defaults to "https://github.com" if not provided.

    Returns
    -------
    str
        The git config command for setting the authentication header.

    Raises
    ------
    ValueError
        If the URL is not a valid GitHub repository URL.

    """
    hostname = urlparse(url).hostname
    if not hostname:
        msg = f"Invalid GitHub URL: {url!r}"
        raise ValueError(msg)

    basic = base64.b64encode(f"x-oauth-basic:{token}".encode()).decode()
    return f"http.https://{hostname}/.extraheader=Authorization: Basic {basic}"


def create_authenticated_url(url: str, token: str | None = None) -> str:
    """Create an authenticated URL for Git operations.

    This is the safest approach for multi-user environments - no global state.

    Parameters
    ----------
    url : str
        The repository URL.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Returns
    -------
    str
        The URL with authentication embedded (for GitHub) or original URL.

    """
    if not (token and is_github_host(url)):
        return url

    parsed = urlparse(url)
    # Add token as username in URL (GitHub supports this)
    netloc = f"x-oauth-basic:{token}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"

    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        ),
    )


@contextmanager
def git_auth_context(url: str, token: str | None = None) -> Generator[tuple[git.Git, str]]:
    """Context manager that provides Git command and authenticated URL.

    Returns both a Git command object and the authenticated URL to use.
    This avoids any global state contamination between users.

    Parameters
    ----------
    url : str
        The repository URL to check if authentication is needed.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Yields
    ------
    Generator[tuple[git.Git, str]]
        Tuple of (Git command object, authenticated URL to use).

    """
    git_cmd = git.Git()
    auth_url = create_authenticated_url(url, token)
    yield git_cmd, auth_url


def validate_github_token(token: str) -> None:
    """Validate the format of a GitHub Personal Access Token.

    Parameters
    ----------
    token : str
        GitHub personal access token (PAT) for accessing private repositories.

    Raises
    ------
    InvalidGitHubTokenError
        If the token format is invalid.

    """
    if not re.fullmatch(_GITHUB_PAT_PATTERN, token):
        raise InvalidGitHubTokenError


async def checkout_partial_clone(config: CloneConfig, token: str | None) -> None:
    """Configure sparse-checkout for a partially cloned repository.

    Parameters
    ----------
    config : CloneConfig
        The configuration for cloning the repository, including subpath and blob flag.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Raises
    ------
    RuntimeError
        If the sparse-checkout configuration fails.

    """
    subpath = config.subpath.lstrip("/")
    if config.blob:
        # Remove the file name from the subpath when ingesting from a file url (e.g. blob/branch/path/file.txt)
        subpath = str(Path(subpath).parent.as_posix())

    try:
        repo = create_git_repo(config.local_path, config.url, token)
        repo.git.sparse_checkout("set", subpath)
    except git.GitCommandError as exc:
        msg = f"Failed to configure sparse-checkout: {exc}"
        raise RuntimeError(msg) from exc


async def resolve_commit(config: CloneConfig, token: str | None) -> str:
    """Resolve the commit to use for the clone.

    Parameters
    ----------
    config : CloneConfig
        The configuration for cloning the repository.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Returns
    -------
    str
        The commit SHA.

    """
    if config.commit:
        commit = config.commit
    elif config.tag:
        commit = await _resolve_ref_to_sha(config.url, pattern=f"refs/tags/{config.tag}*", token=token)
    elif config.branch:
        commit = await _resolve_ref_to_sha(config.url, pattern=f"refs/heads/{config.branch}", token=token)
    else:
        commit = await _resolve_ref_to_sha(config.url, pattern="HEAD", token=token)
    return commit


async def _resolve_ref_to_sha(url: str, pattern: str, token: str | None = None) -> str:
    """Return the commit SHA that <kind>/<ref> points to in <url>.

    * Branch → first line from ``git ls-remote``.
    * Tag    → if annotated, prefer the peeled ``^{}`` line (commit).

    Parameters
    ----------
    url : str
        The URL of the remote repository.
    pattern : str
        The pattern to use to resolve the commit SHA.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Returns
    -------
    str
        The commit SHA.

    Raises
    ------
    ValueError
        If the ref does not exist in the remote repository.

    """
    try:
        # Execute ls-remote command with proper authentication
        with git_auth_context(url, token) as (git_cmd, auth_url):
            output = git_cmd.ls_remote(auth_url, pattern)
        lines = output.splitlines()

        sha = _pick_commit_sha(lines)
        if not sha:
            msg = f"{pattern!r} not found in {url}"
            raise ValueError(msg)

    except git.GitCommandError as exc:
        msg = f"Failed to resolve {pattern} in {url}:\n{exc}"
        raise ValueError(msg) from exc

    return sha


def _pick_commit_sha(lines: Iterable[str]) -> str | None:
    """Return a commit SHA from ``git ls-remote`` output.

    • Annotated tag            →  prefer the peeled line (<sha> refs/tags/x^{})
    • Branch / lightweight tag →  first non-peeled line


    Parameters
    ----------
    lines : Iterable[str]
        The lines of a ``git ls-remote`` output.

    Returns
    -------
    str | None
        The commit SHA, or ``None`` if no commit SHA is found.

    """
    first_non_peeled: str | None = None

    for ln in lines:
        if not ln.strip():
            continue

        sha, ref = ln.split(maxsplit=1)

        if ref.endswith("^{}"):  # peeled commit of annotated tag
            return sha  # ← best match, done

        if first_non_peeled is None:  # remember the first ordinary line
            first_non_peeled = sha

    return first_non_peeled  # branch or lightweight tag (or None)
