"""Tests for the ``git_utils`` module.

These tests validate the ``validate_github_token`` function, which ensures that
GitHub personal access tokens (PATs) are properly formatted.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import pytest

from gitingest.utils.exceptions import InvalidGitHubTokenError
from gitingest.utils.git_utils import create_git_auth_header, create_git_command_with_auth, is_github_host, validate_github_token

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
    ("token", "url", "should_have_auth"),
    [
        (None, "https://github.com/owner/repo.git", False),  # No auth when token is None
        ("ghp_" + "d" * 36, "https://github.com/owner/repo.git", True),  # Auth for GitHub URL + token
        ("ghp_" + "e" * 36, "https://gitlab.com/owner/repo.git", False),  # No auth for non-GitHub URL
    ],
)
def test_create_git_command_with_auth(
    token: str | None,
    url: str,
    should_have_auth: bool,
) -> None:
    """Test that ``create_git_command_with_auth`` creates correct Git objects based on inputs."""
    git_cmd = create_git_command_with_auth(token, url)
    
    # Check if the git command has authentication environment configured
    if should_have_auth:
        assert hasattr(git_cmd, 'custom_environment')
        assert 'GIT_CONFIG_PARAMETERS' in git_cmd.custom_environment
    else:
        # For no auth case, should be basic Git command
        assert not hasattr(git_cmd, 'custom_environment') or 'GIT_CONFIG_PARAMETERS' not in (git_cmd.custom_environment or {})


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
    ("url", "token", "should_have_auth"),
    [
        ("https://github.com/foo/bar.git", "ghp_" + "f" * 36, True),
        ("https://github.com/foo/bar.git", None, False),
        ("https://gitlab.com/foo/bar.git", "ghp_" + "g" * 36, False),
    ],
)
def test_create_git_command_with_auth_calls(
    mocker: MockerFixture,
    tmp_path: Path,
    *,
    url: str,
    token: str | None,
    should_have_auth: bool,
) -> None:
    """Test that ``create_git_auth_header`` is invoked only when appropriate."""
    header_mock = mocker.patch("gitingest.utils.git_utils.create_git_auth_header", return_value="HEADER")

    git_cmd = create_git_command_with_auth(token, url)

    if should_have_auth:
        header_mock.assert_called_once_with(token, url=url)
        assert hasattr(git_cmd, 'custom_environment')
        assert git_cmd.custom_environment['GIT_CONFIG_PARAMETERS'] == "HEADER"
    else:
        header_mock.assert_not_called()


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
    ("token", "url", "expected_auth_hostname"),
    [
        # GitHub.com URLs - should use default hostname
        ("ghp_" + "a" * 36, "https://github.com/owner/repo.git", "github.com"),
        # GitHub Enterprise URLs - should use custom hostname
        ("ghp_" + "b" * 36, "https://github.company.com/owner/repo.git", "github.company.com"),
        ("ghp_" + "c" * 36, "https://github.enterprise.org/owner/repo.git", "github.enterprise.org"),
        ("ghp_" + "d" * 36, "http://github.internal/owner/repo.git", "github.internal"),
    ],
)
def test_create_git_command_with_auth_ghe_urls(
    token: str,
    url: str,
    expected_auth_hostname: str,
) -> None:
    """Test that ``create_git_command_with_auth`` handles GitHub Enterprise URLs correctly."""
    git_cmd = create_git_command_with_auth(token, url)

    # Should have authentication configured
    assert hasattr(git_cmd, 'custom_environment')
    assert 'GIT_CONFIG_PARAMETERS' in git_cmd.custom_environment
    auth_header = git_cmd.custom_environment['GIT_CONFIG_PARAMETERS']

    # Verify the auth header contains the expected hostname
    assert f"http.https://{expected_auth_hostname}/" in auth_header
    assert "Authorization: Basic" in auth_header


@pytest.mark.parametrize(
    ("token", "url"),
    [
        # Should NOT add auth headers for non-GitHub URLs
        ("ghp_" + "a" * 36, "https://gitlab.com/owner/repo.git"),
        ("ghp_" + "b" * 36, "https://bitbucket.org/owner/repo.git"),
        ("ghp_" + "c" * 36, "https://git.example.com/owner/repo.git"),
    ],
)
def test_create_git_command_with_auth_ignores_non_github_urls(
    token: str,
    url: str,
) -> None:
    """Test that ``create_git_command_with_auth`` does not add auth headers for non-GitHub URLs."""
    git_cmd = create_git_command_with_auth(token, url)

    # Should not have authentication configured for non-GitHub URLs
    assert not hasattr(git_cmd, 'custom_environment') or 'GIT_CONFIG_PARAMETERS' not in (git_cmd.custom_environment or {})
