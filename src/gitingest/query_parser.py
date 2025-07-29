"""Module containing functions to parse and validate input sources and patterns."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal

from gitingest.config import TMP_BASE_PATH
from gitingest.schemas import IngestionQuery
from gitingest.utils.git_utils import fetch_remote_branches_or_tags, resolve_commit
from gitingest.utils.logging_config import get_logger
from gitingest.utils.query_parser_utils import (
    PathKind,
    _fallback_to_root,
    _get_user_and_repo_from_path,
    _is_valid_git_commit_hash,
    _normalise_source,
)

# Initialize logger for this module
logger = get_logger(__name__)


async def parse_remote_repo(source: str, token: str | None = None) -> IngestionQuery:
    """Parse a repository URL and return an ``IngestionQuery`` object.

    If source is:
      - A fully qualified URL ('https://gitlab.com/...'), parse & verify that domain
      - A URL missing 'https://' ('gitlab.com/...'), add 'https://' and parse
      - A *slug* ('pandas-dev/pandas'), attempt known domains until we find one that exists.

    Parameters
    ----------
    source : str
        The URL or domain-less slug to parse.
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Returns
    -------
    IngestionQuery
        A dictionary containing the parsed details of the repository.

    """
    parsed_url = await _normalise_source(source, token=token)
    host = parsed_url.netloc
    user, repo = _get_user_and_repo_from_path(parsed_url.path)

    _id = uuid.uuid4()
    slug = f"{user}-{repo}"
    local_path = TMP_BASE_PATH / str(_id) / slug
    url = f"https://{host}/{user}/{repo}"

    query = IngestionQuery(
        host=host,
        user_name=user,
        repo_name=repo,
        url=url,
        local_path=local_path,
        slug=slug,
        id=_id,
    )

    path_parts = parsed_url.path.strip("/").split("/")[2:]

    # main branch
    if not path_parts:
        return await _fallback_to_root(query, token=token)

    kind = PathKind(path_parts.pop(0))  # may raise ValueError
    query.type = kind

    # TODO: Handle issues and pull requests
    if query.type in {PathKind.ISSUES, PathKind.PULL}:
        msg = f"Warning: Issues and pull requests are not yet supported: {url}. Returning repository root."
        return await _fallback_to_root(query, token=token, warn_msg=msg)

    # If no extra path parts, just return
    if not path_parts:
        msg = f"Warning: No extra path parts: {url}. Returning repository root."
        return await _fallback_to_root(query, token=token, warn_msg=msg)

    if query.type not in {PathKind.TREE, PathKind.BLOB}:
        # TODO: Handle other types
        msg = f"Warning: Type '{query.type}' is not yet supported: {url}. Returning repository root."
        return await _fallback_to_root(query, token=token, warn_msg=msg)

    # Commit, branch, or tag
    ref = path_parts[0]

    if _is_valid_git_commit_hash(ref):  # Commit
        query.commit = ref
        path_parts.pop(0)  # Consume the commit hash
    else:  # Branch or tag
        # Try to resolve a tag
        query.tag = await _configure_branch_or_tag(
            path_parts,
            url=url,
            ref_type="tags",
            token=token,
        )

        # If no tag found, try to resolve a branch
        if not query.tag:
            query.branch = await _configure_branch_or_tag(
                path_parts,
                url=url,
                ref_type="branches",
                token=token,
            )

    # Only configure subpath if we have identified a commit, branch, or tag.
    if path_parts and (query.commit or query.branch or query.tag):
        query.subpath += "/".join(path_parts)

    query.commit = await resolve_commit(query.extract_clone_config(), token=token)

    return query


def parse_local_dir_path(path_str: str) -> IngestionQuery:
    """Parse the given file path into a structured query dictionary.

    Parameters
    ----------
    path_str : str
        The file path to parse.

    Returns
    -------
    IngestionQuery
        A dictionary containing the parsed details of the file path.

    """
    path_obj = Path(path_str).resolve()
    slug = path_obj.name if path_str == "." else path_str.strip("/")
    return IngestionQuery(local_path=path_obj, slug=slug, id=uuid.uuid4())


async def _configure_branch_or_tag(
    path_parts: list[str],
    *,
    url: str,
    ref_type: Literal["branches", "tags"],
    token: str | None = None,
) -> str | None:
    """Configure the branch or tag based on the remaining parts of the URL.

    Parameters
    ----------
    path_parts : list[str]
        The path parts of the URL.
    url : str
        The URL of the repository.
    ref_type : Literal["branches", "tags"]
        The type of reference to configure. Can be "branches" or "tags".
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Returns
    -------
    str | None
        The branch or tag name if found, otherwise ``None``.

    """
    _ref_type = "tags" if ref_type == "tags" else "branches"

    try:
        # Fetch the list of branches or tags from the remote repository
        branches_or_tags: list[str] = await fetch_remote_branches_or_tags(url, ref_type=_ref_type, token=token)
    except RuntimeError as exc:
        # If remote discovery fails, we optimistically treat the first path segment as the branch/tag.
        msg = f"Warning: Failed to fetch {_ref_type}: {exc}"
        logger.warning(msg)
        return path_parts.pop(0) if path_parts else None

    # Iterate over the path components and try to find a matching branch/tag
    candidate_parts: list[str] = []

    for part in path_parts:
        candidate_parts.append(part)
        candidate_name = "/".join(candidate_parts)
        if candidate_name in branches_or_tags:
            # We found a match — now consume exactly the parts that form the branch/tag
            del path_parts[: len(candidate_parts)]
            return candidate_name

    # No match found; leave path_parts intact
    return None
