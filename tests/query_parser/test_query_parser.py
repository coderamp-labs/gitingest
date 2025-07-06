"""Tests for the ``query_parser`` module.

These tests cover URL parsing, pattern parsing, and handling of branches/subpaths for HTTP(S) repositories and local
paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

import pytest

from gitingest.query_parser import parse_local_dir_path, parse_remote_repo
from tests.conftest import DEMO_URL

if TYPE_CHECKING:
    from gitingest.schemas import IngestionQuery


URLS_HTTPS: list[str] = [
    DEMO_URL,
    "https://gitlab.com/user/repo",
    "https://bitbucket.org/user/repo",
    "https://gitea.com/user/repo",
    "https://codeberg.org/user/repo",
    "https://gist.github.com/user/repo",
    "https://git.example.com/user/repo",
    "https://gitlab.example.com/user/repo",
    "https://gitlab.example.se/user/repo",
]

URLS_HTTP: list[str] = [url.replace("https://", "http://") for url in URLS_HTTPS]


@pytest.mark.parametrize("url", URLS_HTTPS, ids=lambda u: u)
@pytest.mark.asyncio
async def test_parse_url_valid_https(url: str) -> None:
    """Valid HTTPS URLs parse correctly and ``query.url`` equals the input."""
    query = await _assert_basic_repo_fields(url)

    assert query.url == url  # HTTPS: canonical URL should equal input


@pytest.mark.parametrize("url", URLS_HTTP, ids=lambda u: u)
@pytest.mark.asyncio
async def test_parse_url_valid_http(url: str) -> None:
    """Valid HTTP URLs parse correctly (slug check only)."""
    await _assert_basic_repo_fields(url)


@pytest.mark.asyncio
async def test_parse_url_invalid() -> None:
    """Test ``parse_remote_repo`` with an invalid URL.

    Given an HTTPS URL lacking a repository structure (e.g., "https://github.com"),
    When ``parse_remote_repo`` is called,
    Then a ValueError should be raised indicating an invalid repository URL.
    """
    url = "https://github.com"

    with pytest.raises(ValueError, match="Invalid repository URL"):
        await parse_remote_repo(url)


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [DEMO_URL, "https://gitlab.com/user/repo"])
async def test_parse_query_basic(url: str) -> None:
    """Test ``parse_remote_repo`` with a basic valid repository URL.

    Given an HTTPS URL:
    When ``parse_remote_repo`` is called,
    Then user/repo, URL should be parsed correctly.
    """
    query = await parse_remote_repo(url)

    assert query.user_name == "user"
    assert query.repo_name == "repo"
    assert query.url == url


@pytest.mark.asyncio
async def test_parse_query_mixed_case() -> None:
    """Test ``parse_remote_repo`` with mixed-case URLs.

    Given a URL with mixed-case parts (e.g. "Https://GitHub.COM/UsEr/rEpO"):
    When ``parse_remote_repo`` is called,
    Then the user and repo names should be normalized to lowercase.
    """
    url = "Https://GitHub.COM/UsEr/rEpO"
    query = await parse_remote_repo(url)

    assert query.user_name == "user"
    assert query.repo_name == "repo"


@pytest.mark.asyncio
async def test_parse_url_with_subpaths(stub_branches: Callable[[list[str]], None]) -> None:
    """Test ``parse_remote_repo`` with a URL containing branch and subpath.

    Given a URL referencing a branch ("main") and a subdir ("subdir/file"):
    When ``parse_remote_repo`` is called with remote branch fetching,
    Then user, repo, branch, and subpath should be identified correctly.
    """
    url = DEMO_URL + "/tree/main/subdir/file"

    stub_branches(["main", "dev", "feature-branch"])

    query = await _assert_basic_repo_fields(url)

    assert query.user_name == "user"
    assert query.repo_name == "repo"
    assert query.branch == "main"
    assert query.subpath == "/subdir/file"


@pytest.mark.asyncio
async def test_parse_url_invalid_repo_structure() -> None:
    """Test ``parse_remote_repo`` with a URL missing a repository name.

    Given a URL like "https://github.com/user":
    When ``parse_remote_repo`` is called,
    Then a ValueError should be raised indicating an invalid repository URL.
    """
    url = "https://github.com/user"

    with pytest.raises(ValueError, match="Invalid repository URL"):
        await parse_remote_repo(url)


async def test_parse_local_dir_path_local_path() -> None:
    """Test ``parse_local_dir_path``.

    Given "/home/user/project":
    When ``parse_local_dir_path`` is called,
    Then the local path should be set, id generated, and slug formed accordingly.
    """
    path = "/home/user/project"
    query = parse_local_dir_path(path)
    tail = Path("home/user/project")

    assert query.local_path.parts[-len(tail.parts) :] == tail.parts
    assert query.id is not None
    assert query.slug == "home/user/project"


async def test_parse_local_dir_path_relative_path() -> None:
    """Test ``parse_local_dir_path`` with a relative path.

    Given "./project":
    When ``parse_local_dir_path`` is called,
    Then ``local_path`` resolves relatively, and ``slug`` ends with "project".
    """
    path = "./project"
    query = parse_local_dir_path(path)
    tail = Path("project")

    assert query.local_path.parts[-len(tail.parts) :] == tail.parts
    assert query.slug.endswith("project")


@pytest.mark.asyncio
async def test_parse_remote_repo_empty_source() -> None:
    """Test ``parse_remote_repo`` with an empty string.

    Given an empty source string:
    When ``parse_remote_repo`` is called,
    Then a ValueError should be raised indicating an invalid repository URL.
    """
    url = ""

    with pytest.raises(ValueError, match="Invalid repository URL"):
        await parse_remote_repo(url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "expected_branch", "expected_commit"),
    [
        ("/tree/main", "main", None),
        ("/tree/abcd1234abcd1234abcd1234abcd1234abcd1234", None, "abcd1234abcd1234abcd1234abcd1234abcd1234"),
    ],
)
async def test_parse_url_branch_and_commit_distinction(
    path: str,
    expected_branch: str,
    expected_commit: str,
    stub_branches: Callable[[list[str]], None],
) -> None:
    """Test ``parse_remote_repo`` distinguishing branch vs. commit hash.

    Given either a branch URL (e.g., ".../tree/main") or a 40-character commit URL:
    When ``parse_remote_repo`` is called with branch fetching,
    Then the function should correctly set ``branch`` or ``commit`` based on the URL content.
    """
    stub_branches(["main", "dev", "feature-branch"])

    url = DEMO_URL + path
    query = await _assert_basic_repo_fields(url)

    assert query.branch == expected_branch
    assert query.commit == expected_commit


async def test_parse_local_dir_path_uuid_uniqueness() -> None:
    """Test ``parse_local_dir_path`` for unique UUID generation.

    Given the same path twice:
    When ``parse_local_dir_path`` is called repeatedly,
    Then each call should produce a different query id.
    """
    path = "/home/user/project"
    query_1 = parse_local_dir_path(path)
    query_2 = parse_local_dir_path(path)

    assert query_1.id != query_2.id


@pytest.mark.asyncio
async def test_parse_url_with_query_and_fragment() -> None:
    """Test ``parse_remote_repo`` with query parameters and a fragment.

    Given a URL like "https://github.com/user/repo?arg=value#fragment":
    When ``parse_remote_repo`` is called,
    Then those parts should be stripped, leaving a clean user/repo URL.
    """
    url = DEMO_URL + "?arg=value#fragment"
    query = await parse_remote_repo(url)

    assert query.user_name == "user"
    assert query.repo_name == "repo"
    assert query.url == DEMO_URL  # URL should be cleaned


@pytest.mark.asyncio
async def test_parse_url_unsupported_host() -> None:
    """Test ``parse_remote_repo`` with an unsupported host.

    Given "https://only-domain.com":
    When ``parse_remote_repo`` is called,
    Then a ValueError should be raised for the unknown domain.
    """
    url = "https://only-domain.com"

    with pytest.raises(ValueError, match="Unknown domain 'only-domain.com' in URL"):
        await parse_remote_repo(url)


@pytest.mark.asyncio
async def test_parse_query_with_branch() -> None:
    """Test ``parse_remote_repo`` when a branch is specified in a blob path.

    Given "https://github.com/pandas-dev/pandas/blob/2.2.x/...":
    When ``parse_remote_repo`` is called,
    Then the branch should be identified, subpath set, and commit remain None.
    """
    url = "https://github.com/pandas-dev/pandas/blob/2.2.x/.github/ISSUE_TEMPLATE/documentation_improvement.yaml"
    query = await parse_remote_repo(url)

    assert query.user_name == "pandas-dev"
    assert query.repo_name == "pandas"
    assert query.url == "https://github.com/pandas-dev/pandas"
    assert query.slug == "pandas-dev-pandas"
    assert query.id is not None
    assert query.subpath == "/.github/ISSUE_TEMPLATE/documentation_improvement.yaml"
    assert query.branch == "2.2.x"
    assert query.commit is None
    assert query.type == "blob"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "expected_branch", "expected_subpath"),
    [
        ("/tree/feature/fix1/src", "feature/fix1", "/src"),
        ("/tree/main/src", "main", "/src"),
        ("", None, "/"),
        ("/tree/nonexistent-branch/src", None, "/"),
        ("/tree/fix", "fix", "/"),
        ("/blob/fix/page.html", "fix", "/page.html"),
    ],
)
async def test_parse_repo_source_with_various_url_patterns(
    path: str,
    expected_branch: str | None,
    expected_subpath: str,
    stub_branches: Callable[[list[str]], None],
) -> None:
    """Test ``parse_remote_repo`` with various GitHub-style URL permutations.

    Given various GitHub-style URL permutations:
    When ``parse_remote_repo`` is called,
    Then it should detect (or reject) a branch and resolve the sub-path.

    Branch discovery is stubbed so that only names passed to ``stub_branches`` are considered "remote".
    """
    stub_branches(["feature/fix1", "main", "feature-branch", "fix"])

    url = DEMO_URL + path
    query = await _assert_basic_repo_fields(url)

    assert query.branch == expected_branch
    assert query.subpath == expected_subpath


@pytest.mark.asyncio
async def _assert_basic_repo_fields(url: str) -> IngestionQuery:
    """Run ``parse_remote_repo`` and assert user, repo and slug are parsed."""
    query = await parse_remote_repo(url)

    assert query.user_name == "user"
    assert query.repo_name == "repo"
    assert query.slug == "user-repo"

    return query
