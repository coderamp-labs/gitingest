"""Utility functions for interacting with Git repositories."""

from __future__ import annotations

import asyncio
import base64
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, Iterable
from urllib.parse import urlparse

import httpx
from starlette.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND

from gitingest.utils.colors import Colors
from gitingest.utils.compat_func import removesuffix
from gitingest.utils.exceptions import InvalidGitHubTokenError

if TYPE_CHECKING:
    from gitingest.schemas import CloneConfig

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
        await run_command("git", "--version")
    except RuntimeError as exc:
        msg = "Git is not installed or not accessible. Please install Git first."
        raise RuntimeError(msg) from exc
    if sys.platform == "win32":
        try:
            stdout, _ = await run_command("git", "config", "core.longpaths")
            if stdout.decode().strip().lower() != "true":
                print(
                    f"{Colors.BROWN}WARN{Colors.END}: {Colors.RED}Git clone may fail on Windows "
                    f"due to long file paths:{Colors.END}",
                )
                print(f"{Colors.RED}To avoid this issue, consider enabling long path support with:{Colors.END}")
                print(f"{Colors.RED}    git config --global core.longpaths true{Colors.END}")
                print(f"{Colors.RED}Note: This command may require administrator privileges.{Colors.END}")
        except RuntimeError:
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

    Raises
    ------
    RuntimeError
        If the host returns an unrecognised status code.

    """
    headers = {}

    if token and is_github_host(url):
        host, owner, repo = _parse_github_url(url)
        # Public GitHub vs. GitHub Enterprise
        base_api = "https://api.github.com" if host == "github.com" else f"https://{host}/api/v3"
        url = f"{base_api}/repos/{owner}/{repo}"
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            response = await client.head(url, headers=headers)
        except httpx.RequestError:
            return False

    status_code = response.status_code

    if status_code == HTTP_200_OK:
        return True
    if status_code in {HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND}:
        return False
    msg = f"Unexpected HTTP status {status_code} for {url}"
    raise RuntimeError(msg)


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

    """
    if ref_type not in ("branches", "tags"):
        msg = f"Invalid fetch type: {ref_type}"
        raise ValueError(msg)

    cmd = ["git"]

    # Add authentication if needed
    if token and is_github_host(url):
        cmd += ["-c", create_git_auth_header(token, url=url)]

    cmd += ["ls-remote"]

    fetch_tags = ref_type == "tags"
    to_fetch = "tags" if fetch_tags else "heads"

    cmd += [f"--{to_fetch}"]

    # `--refs` filters out the peeled tag objects (those ending with "^{}") (for tags)
    if fetch_tags:
        cmd += ["--refs"]

    cmd += [url]

    await ensure_git_installed()
    stdout, _ = await run_command(*cmd)
    # For each line in the output:
    # - Skip empty lines and lines that don't contain "refs/{to_fetch}/"
    # - Extract the branch or tag name after "refs/{to_fetch}/"
    return [
        line.split(f"refs/{to_fetch}/", 1)[1]
        for line in stdout.decode().splitlines()
        if line.strip() and f"refs/{to_fetch}/" in line
    ]


def create_git_command(base_cmd: list[str], local_path: str, url: str, token: str | None = None) -> list[str]:
    """Create a git command with authentication if needed.

    Parameters
    ----------
    base_cmd : list[str]
        The base git command to start with.
    local_path : str
        The local path where the git command should be executed.
    url : str
        The repository URL to check if it's a GitHub repository.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Returns
    -------
    list[str]
        The git command with authentication if needed.

    """
    cmd = [*base_cmd, "-C", local_path]
    if token and is_github_host(url):
        cmd += ["-c", create_git_auth_header(token, url=url)]
    return cmd


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

    """
    subpath = config.subpath.lstrip("/")
    if config.blob:
        # Remove the file name from the subpath when ingesting from a file url (e.g. blob/branch/path/file.txt)
        subpath = str(Path(subpath).parent.as_posix())
    checkout_cmd = create_git_command(["git"], config.local_path, config.url, token)
    await run_command(*checkout_cmd, "sparse-checkout", "set", subpath)


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
    # Build: git [-c http.<host>/.extraheader=Auth...] ls-remote <url> <pattern>
    cmd: list[str] = ["git"]
    if token and is_github_host(url):
        cmd += ["-c", create_git_auth_header(token, url=url)]

    cmd += ["ls-remote", url, pattern]
    stdout, _ = await run_command(*cmd)
    lines = stdout.decode().splitlines()
    sha = _pick_commit_sha(lines)
    if not sha:
        msg = f"{pattern!r} not found in {url}"
        raise ValueError(msg)

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
