"""Tests for the ``clone`` module.

These tests cover various scenarios for cloning repositories, verifying that the appropriate Git commands are invoked
and handling edge cases such as nonexistent URLs, timeouts, redirects, and specific commits or branches.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import httpx
import pytest
from starlette.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND

from gitingest.clone import clone_repo
from gitingest.schemas import CloneConfig
from gitingest.utils.git_utils import check_repo_exists
from tests.conftest import DEMO_URL, LOCAL_REPO_PATH

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


# All cloning-related tests assume (unless explicitly overridden) that the repository exists.
# Apply the check-repo patch automatically so individual tests don't need to repeat it.
pytestmark = pytest.mark.usefixtures("repo_exists_true")

GIT_INSTALLED_CALLS = 2 if sys.platform == "win32" else 1


@pytest.mark.asyncio
async def test_clone_with_commit(repo_exists_true: AsyncMock, gitpython_mocks: dict) -> None:
    """Test cloning a repository with a specific commit hash.

    Given a valid URL and a commit hash:
    When ``clone_repo`` is called,
    Then the repository should be cloned and checked out at that commit.
    """
    commit_hash = "a" * 40  # Simulating a valid commit hash
    clone_config = CloneConfig(
        url=DEMO_URL,
        local_path=LOCAL_REPO_PATH,
        commit=commit_hash,
        branch="main",
    )

    await clone_repo(clone_config)

    repo_exists_true.assert_any_call(clone_config.url, token=None)

    # Verify GitPython calls were made
    mock_git_cmd = gitpython_mocks["git_cmd"]
    mock_repo = gitpython_mocks["repo"]
    mock_clone_from = gitpython_mocks["clone_from"]

    # Should have called version (for ensure_git_installed)
    mock_git_cmd.version.assert_called()

    # Should have called clone_from (since partial_clone=False)
    mock_clone_from.assert_called_once()

    # Should have called fetch and checkout on the repo
    mock_repo.git.fetch.assert_called()
    mock_repo.git.checkout.assert_called_with(commit_hash)


@pytest.mark.asyncio
async def test_clone_nonexistent_repository(repo_exists_true: AsyncMock) -> None:
    """Test cloning a nonexistent repository URL.

    Given an invalid or nonexistent URL:
    When ``clone_repo`` is called,
    Then a ValueError should be raised with an appropriate error message.
    """
    clone_config = CloneConfig(
        url="https://github.com/user/nonexistent-repo",
        local_path=LOCAL_REPO_PATH,
        commit=None,
        branch="main",
    )
    # Override the default fixture behaviour for this test
    repo_exists_true.return_value = False

    with pytest.raises(ValueError, match="Repository not found"):
        await clone_repo(clone_config)

    repo_exists_true.assert_any_call(clone_config.url, token=None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (HTTP_200_OK, True),
        (HTTP_401_UNAUTHORIZED, False),
        (HTTP_403_FORBIDDEN, False),
        (HTTP_404_NOT_FOUND, False),
    ],
)
async def test_check_repo_exists(status_code: int, *, expected: bool, mocker: MockerFixture) -> None:
    """Verify that ``check_repo_exists`` interprets httpx results correctly."""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client  # context-manager protocol
    mock_client.head.return_value = httpx.Response(status_code=status_code)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    result = await check_repo_exists(DEMO_URL)

    assert result is expected


@pytest.mark.asyncio
async def test_clone_without_commit(repo_exists_true: AsyncMock, gitpython_mocks: dict) -> None:
    """Test cloning a repository when no commit hash is provided.

    Given a valid URL and no commit hash:
    When ``clone_repo`` is called,
    Then the repository should be cloned and checked out at the resolved commit.
    """
    clone_config = CloneConfig(url=DEMO_URL, local_path=LOCAL_REPO_PATH, commit=None, branch="main")

    await clone_repo(clone_config)

    repo_exists_true.assert_any_call(clone_config.url, token=None)

    # Verify GitPython calls were made
    mock_git_cmd = gitpython_mocks["git_cmd"]
    mock_repo = gitpython_mocks["repo"]
    mock_clone_from = gitpython_mocks["clone_from"]

    # Should have resolved the commit via ls_remote
    mock_git_cmd.ls_remote.assert_called()
    # Should have cloned the repo
    mock_clone_from.assert_called_once()
    # Should have fetched and checked out
    mock_repo.git.fetch.assert_called()
    mock_repo.git.checkout.assert_called()


@pytest.mark.asyncio
async def test_clone_creates_parent_directory(tmp_path: Path, gitpython_mocks: dict) -> None:
    """Test that ``clone_repo`` creates parent directories if they don't exist.

    Given a local path with non-existent parent directories:
    When ``clone_repo`` is called,
    Then it should create the parent directories before attempting to clone.
    """
    nested_path = tmp_path / "deep" / "nested" / "path" / "repo"
    clone_config = CloneConfig(url=DEMO_URL, local_path=str(nested_path))

    await clone_repo(clone_config)

    # Verify parent directories were created
    assert nested_path.parent.exists()

    # Verify clone operation happened
    mock_clone_from = gitpython_mocks["clone_from"]
    mock_clone_from.assert_called_once()


@pytest.mark.asyncio
async def test_clone_with_specific_subpath(gitpython_mocks: dict) -> None:
    """Test cloning a repository with a specific subpath.

    Given a valid repository URL and a specific subpath:
    When ``clone_repo`` is called,
    Then the repository should be cloned with sparse checkout enabled.
    """
    subpath = "src/docs"
    clone_config = CloneConfig(url=DEMO_URL, local_path=LOCAL_REPO_PATH, subpath=subpath)

    await clone_repo(clone_config)

    # Verify partial clone (using git.clone instead of Repo.clone_from)
    mock_git_cmd = gitpython_mocks["git_cmd"]
    mock_git_cmd.clone.assert_called()

    # Verify sparse checkout was configured
    mock_repo = gitpython_mocks["repo"]
    mock_repo.git.sparse_checkout.assert_called()


@pytest.mark.asyncio
async def test_clone_with_include_submodules(gitpython_mocks: dict) -> None:
    """Test cloning a repository with submodules included.

    Given a valid URL and ``include_submodules=True``:
    When ``clone_repo`` is called,
    Then the repository should update submodules after cloning.
    """
    clone_config = CloneConfig(url=DEMO_URL, local_path=LOCAL_REPO_PATH, branch="main", include_submodules=True)

    await clone_repo(clone_config)

    # Verify submodule update was called
    mock_repo = gitpython_mocks["repo"]
    mock_repo.git.submodule.assert_called_with("update", "--init", "--recursive", "--depth=1")


@pytest.mark.asyncio
async def test_check_repo_exists_with_redirect(mocker: MockerFixture) -> None:
    """Test ``check_repo_exists`` when a redirect (302) is returned.

    Given a URL that responds with "302 Found":
    When ``check_repo_exists`` is called,
    Then it should return ``False``, indicating the repo is inaccessible.
    """
    mock_exec = mocker.patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"302\n", b"")
    mock_process.returncode = 0  # Simulate successful request
    mock_exec.return_value = mock_process

    repo_exists = await check_repo_exists(DEMO_URL)

    assert repo_exists is False
