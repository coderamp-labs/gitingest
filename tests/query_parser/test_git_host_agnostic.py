"""Tests to verify that the query parser is Git host agnostic.

These tests confirm that ``parse_query`` correctly identifies user/repo pairs and canonical URLs for GitHub, GitLab,
Bitbucket, Gitea, and Codeberg, even if the host is omitted.
"""

from __future__ import annotations

import pytest

from gitingest.config import MAX_FILE_SIZE
from gitingest.query_parser import parse_remote_repo
from gitingest.utils.query_parser_utils import KNOWN_GIT_HOSTS, _is_valid_git_commit_hash

# Repository matrix: (host, user, repo)
_REPOS: list[tuple[str, str, str]] = [
    ("github.com", "fastapi", "fastapi"),
    ("gitlab.com", "gitlab-org", "gitlab-runner"),
    ("bitbucket.org", "na-dna", "llm-knowledge-share"),
    ("gitea.com", "xorm", "xorm"),
    ("codeberg.org", "forgejo", "forgejo"),
    ("git.rwth-aachen.de", "medialab", "19squared"),
    ("gitlab.alpinelinux.org", "alpine", "apk-tools"),
]


# Generate cartesian product of repository tuples with URL variants.
@pytest.mark.parametrize(("host", "user", "repo"), _REPOS, ids=[f"{h}:{u}/{r}" for h, u, r in _REPOS])
@pytest.mark.parametrize("variant", ["full", "noscheme", "slug"])
@pytest.mark.asyncio
async def test_parse_query_without_host(
    host: str,
    user: str,
    repo: str,
    variant: str,
) -> None:
    """Verify that ``parse_remote_repo`` handles URLs, host-omitted URLs and raw slugs."""
    # Build the input URL based on the selected variant
    if variant == "full":
        url = f"https://{host}/{user}/{repo}"
    elif variant == "noscheme":
        url = f"{host}/{user}/{repo}"
    else:  # "slug"
        url = f"{user}/{repo}"

    expected_url = f"https://{host}/{user}/{repo}"

    # For slug form with a custom host (not in KNOWN_GIT_HOSTS) we expect a failure,
    # because the parser cannot guess which domain to use.
    if variant == "slug" and host not in KNOWN_GIT_HOSTS:
        with pytest.raises(ValueError, match="Could not find a valid repository host"):
            await parse_remote_repo(url)
        return

    query = await parse_remote_repo(url)

    # Compare against the canonical dict while ignoring unpredictable fields.
    actual = query.model_dump(exclude={"id", "local_path", "ignore_patterns", "s3_url"})

    assert "commit" in actual
    assert _is_valid_git_commit_hash(actual["commit"])
    del actual["commit"]

    expected = {
        "host": host,
        "user_name": user,
        "repo_name": repo,
        "url": expected_url,
        "slug": f"{user}-{repo}",
        "subpath": "/",
        "type": None,
        "branch": None,
        "tag": None,
        "max_file_size": MAX_FILE_SIZE,
        "include_patterns": None,
        "include_submodules": False,
    }

    assert actual == expected
