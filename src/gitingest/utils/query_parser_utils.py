"""Utility functions for parsing and validating query parameters."""

from __future__ import annotations

import string

HEX_DIGITS: set[str] = set(string.hexdigits)


KNOWN_GIT_HOSTS: list[str] = [
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "gitea.com",
    "codeberg.org",
    "gist.github.com",
]


def _is_valid_git_commit_hash(commit: str) -> bool:
    """Validate if the provided string is a valid Git commit hash.

    This function checks if the commit hash is a 40-character string consisting only
    of hexadecimal digits, which is the standard format for Git commit hashes.

    Parameters
    ----------
    commit : str
        The string to validate as a Git commit hash.

    Returns
    -------
    bool
        ``True`` if the string is a valid 40-character Git commit hash, otherwise ``False``.

    """
    sha_hex_length = 40
    return len(commit) == sha_hex_length and all(c in HEX_DIGITS for c in commit)


def _validate_host(host: str) -> None:
    """Validate a hostname.

    The host is accepted if it is either present in the hard-coded ``KNOWN_GIT_HOSTS`` list or if it satisfies the
    simple heuristics in ``_looks_like_git_host``, which try to recognise common self-hosted Git services (e.g. GitLab
    instances on sub-domains such as 'gitlab.example.com' or 'git.example.com').

    Parameters
    ----------
    host : str
        Hostname (case-insensitive).

    Raises
    ------
    ValueError
        If the host cannot be recognised as a probable Git hosting domain.

    """
    host = host.lower()
    if host not in KNOWN_GIT_HOSTS and not _looks_like_git_host(host):
        msg = f"Unknown domain '{host}' in URL"
        raise ValueError(msg)


def _looks_like_git_host(host: str) -> bool:
    """Check if the given host looks like a Git host.

    The current heuristic returns ``True`` when the host starts with ``git.`` (e.g. 'git.example.com'), starts with
    'gitlab.' (e.g. 'gitlab.company.com'), or starts with 'github.' (e.g. 'github.company.com' for GitHub Enterprise).

    Parameters
    ----------
    host : str
        Hostname (case-insensitive).

    Returns
    -------
    bool
        ``True`` if the host looks like a Git host, otherwise ``False``.

    """
    host = host.lower()
    return host.startswith(("git.", "gitlab.", "github."))


def _validate_url_scheme(scheme: str) -> None:
    """Validate the given scheme against the known schemes.

    Parameters
    ----------
    scheme : str
        The scheme to validate.

    Raises
    ------
    ValueError
        If the scheme is not 'http' or 'https'.

    """
    scheme = scheme.lower()
    if scheme not in ("https", "http"):
        msg = f"Invalid URL scheme '{scheme}' in URL"
        raise ValueError(msg)


def _get_user_and_repo_from_path(path: str) -> tuple[str, str]:
    """Extract the user and repository names from a given path.

    Parameters
    ----------
    path : str
        The path to extract the user and repository names from.

    Returns
    -------
    tuple[str, str]
        A tuple containing the user and repository names.

    Raises
    ------
    ValueError
        If the path does not contain at least two parts.

    """
    min_path_parts = 2
    path_parts = path.lower().strip("/").split("/")
    if len(path_parts) < min_path_parts:
        msg = f"Invalid repository URL '{path}'"
        raise ValueError(msg)
    return path_parts[0], path_parts[1]
