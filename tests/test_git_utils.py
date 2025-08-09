"""Tests for the ``git_utils`` module.

These tests validate the ``validate_github_token`` function, which ensures that
GitHub personal access tokens (PATs) are properly formatted.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import pytest

from gitingest.utils.exceptions import InvalidGitHubTokenError
from gitingest.utils.git_utils import create_git_auth_header, create_git_command, is_github_host, validate_github_token

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
    ("base_cmd", "local_path", "url", "token", "expected_suffix"),
    [
        (
            ["git", "clone"],
            "/some/path",
            "https://github.com/owner/repo.git",
            None,
            [],  # No auth header expected when token is None
        ),
        (
            ["git", "clone"],
            "/some/path",
            "https://github.com/owner/repo.git",
            "ghp_" + "d" * 36,
            [
                "-c",
                create_git_auth_header("ghp_" + "d" * 36),
            ],  # Auth header expected for GitHub URL + token
        ),
        (
            ["git", "clone"],
            "/some/path",
            "https://gitlab.com/owner/repo.git",
            "ghp_" + "e" * 36,
            [],  # No auth header for non-GitHub URL even if token provided
        ),
    ],
)
def test_create_git_command(
    base_cmd: list[str],
    local_path: str,
    url: str,
    token: str | None,
    expected_suffix: list[str],
) -> None:
    """Test that ``create_git_command`` builds the correct command list based on inputs."""
    cmd = create_git_command(base_cmd, local_path, url, token)

    # The command should start with base_cmd and the -C option
    expected_prefix = [*base_cmd, "-C", local_path]
    assert cmd[: len(expected_prefix)] == expected_prefix

    # The suffix (anything after prefix) should match expected
    assert cmd[len(expected_prefix) :] == expected_suffix


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
def test_create_git_command_helper_calls(
    mocker: MockerFixture,
    tmp_path: Path,
    *,
    url: str,
    token: str | None,
    should_call: bool,
) -> None:
    """Test that ``create_git_auth_header`` is invoked only when appropriate."""
    work_dir = tmp_path / "repo"
    header_mock = mocker.patch("gitingest.utils.git_utils.create_git_auth_header", return_value="HEADER")

    cmd = create_git_command(["git", "clone"], str(work_dir), url, token)

    if should_call:
        header_mock.assert_called_once_with(token, url=url)
        assert "HEADER" in cmd
    else:
        header_mock.assert_not_called()
        assert "HEADER" not in cmd


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
    ("base_cmd", "local_path", "url", "token", "expected_auth_hostname"),
    [
        # GitHub.com URLs - should use default hostname
        (
            ["git", "clone"],
            "/some/path",
            "https://github.com/owner/repo.git",
            "ghp_" + "a" * 36,
            "github.com",
        ),
        # GitHub Enterprise URLs - should use custom hostname
        (
            ["git", "clone"],
            "/some/path",
            "https://github.company.com/owner/repo.git",
            "ghp_" + "b" * 36,
            "github.company.com",
        ),
        (
            ["git", "clone"],
            "/some/path",
            "https://github.enterprise.org/owner/repo.git",
            "ghp_" + "c" * 36,
            "github.enterprise.org",
        ),
        (
            ["git", "clone"],
            "/some/path",
            "http://github.internal/owner/repo.git",
            "ghp_" + "d" * 36,
            "github.internal",
        ),
    ],
)
def test_create_git_command_with_ghe_urls(
    base_cmd: list[str],
    local_path: str,
    url: str,
    token: str,
    expected_auth_hostname: str,
) -> None:
    """Test that ``create_git_command`` handles GitHub Enterprise URLs correctly."""
    cmd = create_git_command(base_cmd, local_path, url, token)

    # Should have base command and -C option
    expected_prefix = [*base_cmd, "-C", local_path]
    assert cmd[: len(expected_prefix)] == expected_prefix

    # Should have -c and auth header
    assert "-c" in cmd
    auth_header_index = cmd.index("-c") + 1
    auth_header = cmd[auth_header_index]

    # Verify the auth header contains the expected hostname
    assert f"http.https://{expected_auth_hostname}/" in auth_header
    assert "Authorization: Basic" in auth_header


@pytest.mark.parametrize(
    ("base_cmd", "local_path", "url", "token"),
    [
        # Should NOT add auth headers for non-GitHub URLs
        (["git", "clone"], "/some/path", "https://gitlab.com/owner/repo.git", "ghp_" + "a" * 36),
        (["git", "clone"], "/some/path", "https://bitbucket.org/owner/repo.git", "ghp_" + "b" * 36),
        (["git", "clone"], "/some/path", "https://git.example.com/owner/repo.git", "ghp_" + "c" * 36),
    ],
)
def test_create_git_command_ignores_non_github_urls(
    base_cmd: list[str],
    local_path: str,
    url: str,
    token: str,
) -> None:
    """Test that ``create_git_command`` does not add auth headers for non-GitHub URLs."""
    cmd = create_git_command(base_cmd, local_path, url, token)

    # Should only have base command and -C option, no auth headers
    expected = [*base_cmd, "-C", local_path]
    assert cmd == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not-a-url",
        "ftp://github.com/owner/repo.git",
        "github.com/owner/repo.git",
        "https://",
    ],
)
def test_is_github_host_edge_cases(url: str) -> None:
    """Test is_github_host with malformed or edge-case URLs."""
    try:
        result = is_github_host(url)
        assert isinstance(result, bool)
    except (ValueError, TypeError) as exc:
        pytest.fail(f"is_github_host raised {exc.__class__.__name__} for url: {url}")


def test_token_not_in_command_plaintext() -> None:
    """Ensure the token is not present in the command as plain text."""
    token = "ghp_" + "x" * 36
    cmd = create_git_command(["git", "clone"], "/tmp", "https://github.com/owner/repo.git", token)
    for part in cmd:
        assert token not in part or "Basic" in part
