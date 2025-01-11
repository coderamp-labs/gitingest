""" This module contains functions to parse and validate input sources and patterns. """

import os
import re
import string
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from config import TMP_BASE_PATH
from gitingest.exceptions import InvalidPatternError
from gitingest.ignore_patterns import DEFAULT_IGNORE_PATTERNS
from gitingest.repository_clone import _check_repo_exists

HEX_DIGITS: set[str] = set(string.hexdigits)

KNOWN_GIT_HOSTS: list[str] = [
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "gitea.com",
    "codeberg.org",
]


async def parse_query(
    source: str,
    max_file_size: int,
    from_web: bool,
    include_patterns: list[str] | str | None = None,
    ignore_patterns: list[str] | str | None = None,
) -> dict[str, Any]:
    """
    Parse the input source to construct a query dictionary with specified parameters.

    This function processes the provided source (either a URL or file path) and builds a
    query dictionary that includes information such as the source URL, maximum file size,
    and any patterns to include or ignore. It handles both web and file-based sources.

    Parameters
    ----------
    source : str
        The source URL or file path to parse.
    max_file_size : int
        The maximum file size in bytes to include.
    from_web : bool
        Flag indicating whether the source is a web URL.
    include_patterns : list[str] | str | None, optional
        Patterns to include, by default None. Can be a list of strings or a single string.
    ignore_patterns : list[str] | str | None, optional
        Patterns to ignore, by default None. Can be a list of strings or a single string.

    Returns
    -------
    dict[str, Any]
        A dictionary containing the parsed query parameters, including 'max_file_size',
        'ignore_patterns', and 'include_patterns'.
    """

    # Determine the parsing method based on the source type
    if from_web or urlparse(source).scheme in ("https", "http") or any(h in source for h in KNOWN_GIT_HOSTS):
        # We either have a full URL or a domain-less slug
        query = await _parse_repo_source(source)
    else:
        # Local path scenario
        query = _parse_path(source)

    # Combine ignore patterns
    ignore_patterns_list = DEFAULT_IGNORE_PATTERNS.copy()
    if ignore_patterns:
        ignore_patterns_list += _parse_patterns(ignore_patterns)

    # Process include patterns and override ignore patterns accordingly
    if include_patterns:
        parsed_include = _parse_patterns(include_patterns)
        ignore_patterns_list = _override_ignore_patterns(ignore_patterns_list, include_patterns=parsed_include)
    else:
        parsed_include = None

    query.update(
        {
            "max_file_size": max_file_size,
            "ignore_patterns": ignore_patterns_list,
            "include_patterns": parsed_include,
        }
    )
    return query


async def _parse_repo_source(source: str) -> dict[str, Any]:
    """
    Parse a repository URL into a structured query dictionary.

    If source is:
      - A fully qualified URL (https://gitlab.com/...), parse & verify that domain
      - A URL missing 'https://' (gitlab.com/...), add 'https://' and parse
      - A 'slug' (like 'pandas-dev/pandas'), attempt known domains until we find one that exists.

    Parameters
    ----------
    source : str
        The URL or domain-less slug to parse.

    Returns
    -------
    dict[str, Any]
        A dictionary containing the parsed details of the repository, including the username,
        repository name, commit, branch, and other relevant information.
    """
    source = unquote(source)

    # Attempt to parse
    parsed_url = urlparse(source)

    if parsed_url.scheme:
        _validate_scheme(parsed_url.scheme)
        _validate_host(parsed_url.netloc.lower())

    else:  # Will be of the form 'host/user/repo' or 'user/repo'
        tmp_host = source.split("/")[0].lower()
        if "." in tmp_host:
            _validate_host(tmp_host)
        else:
            # No scheme, no domain => user typed "user/repo", so we'll guess the domain.
            host = await try_domains_for_user_and_repo(*_get_user_and_repo_from_path(source))
            source = f"{host}/{source}"

        source = "https://" + source
        parsed_url = urlparse(source)

    host = parsed_url.netloc.lower()
    user_name, repo_name = _get_user_and_repo_from_path(parsed_url.path)

    _id = str(uuid.uuid4())
    slug = f"{user_name}-{repo_name}"
    local_path = Path(TMP_BASE_PATH) / _id / slug
    url = f"https://{host}/{user_name}/{repo_name}"

    parsed = {
        "user_name": user_name,
        "repo_name": repo_name,
        "type": None,
        "branch": None,
        "commit": None,
        "subpath": "/",
        "local_path": local_path,
        "url": url,
        "slug": slug,  # e.g. "pandas-dev-pandas"
        "id": _id,
    }

    remaining_parts = parsed_url.path.strip("/").split("/")[2:]

    if not remaining_parts:
        return parsed

    possible_type = remaining_parts.pop(0)  # e.g. 'issues', 'pull', 'tree', 'blob'

    # If no extra path parts, just return
    if not remaining_parts:
        return parsed

    # If this is an issues page or pull requests, return early without processing subpath
    if remaining_parts and possible_type in ("issues", "pull"):
        return parsed

    parsed["type"] = possible_type

    # Commit or branch
    commit_or_branch = remaining_parts.pop(0)
    if _is_valid_git_commit_hash(commit_or_branch):
        parsed["commit"] = commit_or_branch
    else:
        parsed["branch"] = commit_or_branch

    # Subpath if anything left
    if remaining_parts:
        parsed["subpath"] += "/".join(remaining_parts)

    return parsed


def _is_valid_git_commit_hash(commit: str) -> bool:
    """
    Validate if the provided string is a valid Git commit hash.

    This function checks if the commit hash is a 40-character string consisting only
    of hexadecimal digits, which is the standard format for Git commit hashes.

    Parameters
    ----------
    commit : str
        The string to validate as a Git commit hash.

    Returns
    -------
    bool
        True if the string is a valid 40-character Git commit hash, otherwise False.
    """
    return len(commit) == 40 and all(c in HEX_DIGITS for c in commit)


def _normalize_pattern(pattern: str) -> str:
    """
    Normalize the given pattern by removing leading separators and appending a wildcard.

    This function processes the pattern string by stripping leading directory separators
    and appending a wildcard (`*`) if the pattern ends with a separator.

    Parameters
    ----------
    pattern : str
        The pattern to normalize.

    Returns
    -------
    str
        The normalized pattern.
    """
    pattern = pattern.lstrip(os.sep)
    if pattern.endswith(os.sep):
        pattern += "*"
    return pattern


def _parse_patterns(pattern: list[str] | str) -> list[str]:
    """
    Parse and validate file/directory patterns for inclusion or exclusion.

    Takes either a single pattern string or list of pattern strings and processes them into a normalized list.
    Patterns are split on commas and spaces, validated for allowed characters, and normalized.

    Parameters
    ----------
    pattern : list[str] | str
        Pattern(s) to parse - either a single string or list of strings

    Returns
    -------
    list[str]
        List of normalized pattern strings

    Raises
    ------
    InvalidPatternError
        If any pattern contains invalid characters. Only alphanumeric characters,
        dash (-), underscore (_), dot (.), forward slash (/), plus (+), and
        asterisk (*) are allowed.
    """
    patterns = pattern if isinstance(pattern, list) else [pattern]

    parsed_patterns = []
    for p in patterns:
        parsed_patterns.extend(re.split(",| ", p))

    # Filter out any empty strings
    parsed_patterns = [p for p in parsed_patterns if p != ""]

    # Validate and normalize each pattern
    for p in parsed_patterns:
        if not _is_valid_pattern(p):
            raise InvalidPatternError(p)

    return [_normalize_pattern(p) for p in parsed_patterns]


def _override_ignore_patterns(ignore_patterns: list[str], include_patterns: list[str]) -> list[str]:
    """
    Remove patterns from ignore_patterns that are present in include_patterns using set difference.

    Parameters
    ----------
    ignore_patterns : list[str]
        The list of patterns to potentially remove.
    include_patterns : list[str]
        The list of patterns to exclude from ignore_patterns.

    Returns
    -------
    list[str]
        A new list of ignore_patterns with specified patterns removed.
    """
    return list(set(ignore_patterns) - set(include_patterns))


def _parse_path(path_str: str) -> dict[str, Any]:
    """
    Parse a file path into a structured query dictionary.

    This function takes a file path and constructs a query dictionary that includes
    relevant details such as the absolute path and the slug (a combination of the
    directory and file names).

    Parameters
    ----------
    path_str : str
        The file path to parse.

    Returns
    -------
    dict[str, Any]
        A dictionary containing parsed details such as the local file path and slug.
    """
    path_obj = Path(path_str).resolve()
    query = {
        "url": None,
        "local_path": path_obj,
        "slug": f"{path_obj.parent.name}/{path_obj.name}",
        "subpath": "/",
        "id": str(uuid.uuid4()),
    }
    return query


def _is_valid_pattern(pattern: str) -> bool:
    """
    Validate if the given pattern contains only valid characters.

    This function checks if the pattern contains only alphanumeric characters or one
    of the following allowed characters: dash (`-`), underscore (`_`), dot (`.`),
    forward slash (`/`), plus (`+`), or asterisk (`*`).

    Parameters
    ----------
    pattern : str
        The pattern to validate.

    Returns
    -------
    bool
        True if the pattern is valid, otherwise False.
    """
    return all(c.isalnum() or c in "-_./+*" for c in pattern)


async def try_domains_for_user_and_repo(user_name: str, repo_name: str) -> str:
    """
    Attempt to find a valid repository host for the given user_name and repo_name.

    Parameters
    ----------
    user_name : str
        The username or owner of the repository.
    repo_name : str
        The name of the repository.

    Returns
    -------
    str
        The domain of the valid repository host.

    Raises
    ------
    ValueError
        If no valid repository host is found for the given user_name and repo_name.
    """
    for domain in KNOWN_GIT_HOSTS:
        candidate = f"https://{domain}/{user_name}/{repo_name}"
        if await _check_repo_exists(candidate):
            return domain
    raise ValueError(f"Could not find a valid repository host for '{user_name}/{repo_name}'.")


def _get_user_and_repo_from_path(path: str) -> tuple[str, str]:
    """
    Extract the user and repository names from a given path.

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
    path_parts = path.lower().strip("/").split("/")
    if len(path_parts) < 2:
        raise ValueError(f"Invalid repository URL '{path}'")
    return path_parts[0], path_parts[1]


def _validate_host(host: str) -> None:
    """
    Validate the given host against the known Git hosts.

    Parameters
    ----------
    host : str
        The host to validate.

    Raises
    ------
    ValueError
        If the host is not a known Git host.
    """
    if host not in KNOWN_GIT_HOSTS:
        raise ValueError(f"Unknown domain '{host}' in URL")


def _validate_scheme(scheme: str) -> None:
    """
    Validate the given scheme against the known schemes.

    Parameters
    ----------
    scheme : str
        The scheme to validate.

    Raises
    ------
    ValueError
        If the scheme is not 'http' or 'https'.
    """
    if scheme not in ("https", "http"):
        raise ValueError(f"Invalid URL scheme '{scheme}' in URL")
