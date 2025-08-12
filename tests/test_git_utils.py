"""Tests for the ``git_utils`` module.

These tests validate the ``validate_github_token`` function, which ensures that
GitHub personal access tokens (PATs) are properly formatted.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import pytest

from gitingest.utils.exceptions import InvalidGitHubTokenError
from gitingest.utils.git_utils import create_git_auth_header, create_git_repo, is_github_host, validate_github_token

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    "token",
    [
        # Valid tokens: correct prefixes and at least 36 allowed characters afterwards
        "github_pat_" + "a" * 22 + "_" + "b" * 59,
        "ghp_" + "A" * 36,
        "ghu_" + "B" * 36,
        "ghs_" + "C" * 36,
        "ghr_" + "D" * 36,
        "gho_" + "E" * 36,
    ],
)
def test_validate_github_token_valid(token: str) -> None:
    """validate_github_token should accept properly-formatted tokens."""
    # Should not raise any exception
    validate_github_token(token)


@pytest.mark.parametrize(
    "token",
    [
        "github_pat_short",  # Too short after prefix
        "ghp_" + "b" * 35,  # one character short
        "invalidprefix_" + "c" * 36,  # Wrong prefix
        "github_pat_" + "!" * 36,  # Disallowed characters
        "github_pat_" + "a" * 36,  # Too short after 'github_pat_' prefix
        "",  # Empty string
    ],
)
def test_validate_github_token_invalid(token: str) -> None:
    """Test that ``validate_github_token`` raises ``InvalidGitHubTokenError`` on malformed tokens."""
    with pytest.raises(InvalidGitHubTokenError):
        validate_github_token(token)


@pytest.mark.parametrize(
    ("local_path", "url", "token", "should_configure_auth"),
    [
        (
            "/some/path",
            "https://github.com/owner/repo.git",
            None,
            False,  # No auth configuration expected when token is None
        ),
        (
            "/some/path",
            "https://github.com/owner/repo.git",
            "ghp_" + "d" * 36,
            True,  # Auth configuration expected for GitHub URL + token
        ),
        (
            "/some/path",
            "https://gitlab.com/owner/repo.git",
            "ghp_" + "e" * 36,
            False,  # No auth configuration for non-GitHub URL even if token provided
        ),
    ],
)
def test_create_git_repo(
    local_path: str,
    url: str,
    token: str | None,
    should_configure_auth: bool,  # noqa: FBT001
    mocker: MockerFixture,
) -> None:
    """Test that ``create_git_repo`` creates a proper Git repo object."""
    # Mock git.Repo to avoid actual filesystem operations
    mock_repo = mocker.MagicMock()
    mock_repo_class = mocker.patch("git.Repo", return_value=mock_repo)

    repo = create_git_repo(local_path, url, token)

    # Should create repo with correct path
    mock_repo_class.assert_called_once_with(local_path)
    assert repo == mock_repo

    # Check auth configuration
    if should_configure_auth:
        mock_repo.git.config.assert_called_once()
    else:
        mock_repo.git.config.assert_not_called()


@pytest.mark.parametrize(
    "token",
    [
        "ghp_abcdefghijklmnopqrstuvwxyz012345",  # typical ghp_ token
        "github_pat_1234567890abcdef1234567890abcdef1234",
    ],
)
def test_create_git_auth_header(token: str) -> None:
    """Test that ``create_git_auth_header`` produces correct base64-encoded header."""
    header = create_git_auth_header(token)
    expected_basic = base64.b64encode(f"x-oauth-basic:{token}".encode()).decode()
    expected = f"http.https://github.com/.extraheader=Authorization: Basic {expected_basic}"
    assert header == expected


@pytest.mark.parametrize(
    ("url", "token", "should_call"),
    [
        ("https://github.com/foo/bar.git", "ghp_" + "f" * 36, True),
        ("https://github.com/foo/bar.git", None, False),
        ("https://gitlab.com/foo/bar.git", "ghp_" + "g" * 36, False),
    ],
)
def test_create_git_repo_helper_calls(
    mocker: MockerFixture,
    tmp_path: Path,
    *,
    url: str,
    token: str | None,
    should_call: bool,
) -> None:
    """Test that ``create_git_auth_header`` is invoked only when appropriate."""
    work_dir = tmp_path / "repo"
    header_mock = mocker.patch("gitingest.utils.git_utils.create_git_auth_header", return_value="key=value")
    mock_repo = mocker.MagicMock()
    mocker.patch("git.Repo", return_value=mock_repo)

    create_git_repo(str(work_dir), url, token)

    if should_call:
        header_mock.assert_called_once_with(token, url=url)
        mock_repo.git.config.assert_called_once_with("key", "value")
    else:
        header_mock.assert_not_called()
        mock_repo.git.config.assert_not_called()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # GitHub.com URLs
        ("https://github.com/owner/repo.git", True),
        ("http://github.com/owner/repo.git", True),
        ("https://github.com/owner/repo", True),
        # GitHub Enterprise URLs
        ("https://github.company.com/owner/repo.git", True),
        ("https://github.enterprise.org/owner/repo.git", True),
        ("http://github.internal/owner/repo.git", True),
        ("https://github.example.co.uk/owner/repo.git", True),
        # Non-GitHub URLs
        ("https://gitlab.com/owner/repo.git", False),
        ("https://bitbucket.org/owner/repo.git", False),
        ("https://git.example.com/owner/repo.git", False),
        ("https://mygithub.com/owner/repo.git", False),  # doesn't start with "github."
        ("https://subgithub.com/owner/repo.git", False),
        ("https://example.com/github/repo.git", False),
        # Edge cases
        ("", False),
        ("not-a-url", False),
        ("ftp://github.com/owner/repo.git", True),  # Different protocol but still github.com
    ],
)
def test_is_github_host(url: str, *, expected: bool) -> None:
    """Test that ``is_github_host`` correctly identifies GitHub and GitHub Enterprise URLs."""
    assert is_github_host(url) == expected


@pytest.mark.parametrize(
    ("token", "url", "expected_hostname"),
    [
        # GitHub.com URLs (default)
        ("ghp_" + "a" * 36, "https://github.com", "github.com"),
        ("ghp_" + "a" * 36, "https://github.com/owner/repo.git", "github.com"),
        # GitHub Enterprise URLs
        ("ghp_" + "b" * 36, "https://github.company.com", "github.company.com"),
        ("ghp_" + "c" * 36, "https://github.enterprise.org/owner/repo.git", "github.enterprise.org"),
        ("ghp_" + "d" * 36, "http://github.internal", "github.internal"),
    ],
)
def test_create_git_auth_header_with_ghe_url(token: str, url: str, expected_hostname: str) -> None:
    """Test that ``create_git_auth_header`` handles GitHub Enterprise URLs correctly."""
    header = create_git_auth_header(token, url=url)
    expected_basic = base64.b64encode(f"x-oauth-basic:{token}".encode()).decode()
    expected = f"http.https://{expected_hostname}/.extraheader=Authorization: Basic {expected_basic}"
    assert header == expected


@pytest.mark.parametrize(
    ("local_path", "url", "token", "expected_auth_hostname"),
    [
        # GitHub.com URLs - should use default hostname
        (
            "/some/path",
            "https://github.com/owner/repo.git",
            "ghp_" + "a" * 36,
            "github.com",
        ),
        # GitHub Enterprise URLs - should use custom hostname
        (
            "/some/path",
            "https://github.company.com/owner/repo.git",
            "ghp_" + "b" * 36,
            "github.company.com",
        ),
        (
            "/some/path",
            "https://github.enterprise.org/owner/repo.git",
            "ghp_" + "c" * 36,
            "github.enterprise.org",
        ),
        (
            "/some/path",
            "http://github.internal/owner/repo.git",
            "ghp_" + "d" * 36,
            "github.internal",
        ),
    ],
)
def test_create_git_repo_with_ghe_urls(
    local_path: str,
    url: str,
    token: str,
    expected_auth_hostname: str,
    mocker: MockerFixture,
) -> None:
    """Test that ``create_git_repo`` handles GitHub Enterprise URLs correctly."""
    mock_repo = mocker.MagicMock()
    mocker.patch("git.Repo", return_value=mock_repo)

    create_git_repo(local_path, url, token)

    # Should configure auth with the correct hostname
    mock_repo.git.config.assert_called_once()
    auth_config_call = mock_repo.git.config.call_args[0]

    # The first argument should contain the hostname
    assert expected_auth_hostname in auth_config_call[0]


@pytest.mark.parametrize(
    ("local_path", "url", "token"),
    [
        # Should NOT configure auth for non-GitHub URLs
        ("/some/path", "https://gitlab.com/owner/repo.git", "ghp_" + "a" * 36),
        ("/some/path", "https://bitbucket.org/owner/repo.git", "ghp_" + "b" * 36),
        ("/some/path", "https://git.example.com/owner/repo.git", "ghp_" + "c" * 36),
    ],
)
def test_create_git_repo_ignores_non_github_urls(
    local_path: str,
    url: str,
    token: str,
    mocker: MockerFixture,
) -> None:
    """Test that ``create_git_repo`` does not configure auth for non-GitHub URLs."""
    mock_repo = mocker.MagicMock()
    mocker.patch("git.Repo", return_value=mock_repo)

    create_git_repo(local_path, url, token)

    # Should not configure auth for non-GitHub URLs
    mock_repo.git.config.assert_not_called()
