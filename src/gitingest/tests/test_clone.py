from unittest.mock import AsyncMock, patch

import pytest

from gitingest.clone import CloneConfig, _check_repo_exists, clone_repo


@pytest.mark.asyncio
async def test_clone_repo_with_commit() -> None:
    clone_config = CloneConfig(
        url="https://github.com/user/repo",
        local_path="/tmp/repo",
        commit="a" * 40,  # Simulating a valid commit hash
        branch="main",
    )

    with patch("gitingest.clone._check_repo_exists", return_value=True) as mock_check:
        with patch("gitingest.clone._run_git_command", new_callable=AsyncMock) as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"output", b"error")
            mock_exec.return_value = mock_process
            await clone_repo(clone_config)
            mock_check.assert_called_once_with(clone_config.url)
            assert mock_exec.call_count == 2  # Clone and checkout calls


@pytest.mark.asyncio
async def test_clone_repo_without_commit() -> None:
    query = CloneConfig(url="https://github.com/user/repo", local_path="/tmp/repo", commit=None, branch="main")

    with patch("gitingest.clone._check_repo_exists", return_value=True) as mock_check:
        with patch("gitingest.clone._run_git_command", new_callable=AsyncMock) as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"output", b"error")
            mock_exec.return_value = mock_process

            await clone_repo(query)
            mock_check.assert_called_once_with(query.url)
            assert mock_exec.call_count == 1  # Only clone call


@pytest.mark.asyncio
async def test_clone_repo_nonexistent_repository() -> None:
    clone_config = CloneConfig(
        url="https://github.com/user/nonexistent-repo",
        local_path="/tmp/repo",
        commit=None,
        branch="main",
    )
    with patch("gitingest.clone._check_repo_exists", return_value=False) as mock_check:
        with pytest.raises(ValueError, match="Repository not found"):
            await clone_repo(clone_config)
            mock_check.assert_called_once_with(clone_config.url)


@pytest.mark.asyncio
async def test_check_repo_exists() -> None:
    url = "https://github.com/user/repo"

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"HTTP/1.1 200 OK\n", b"")
        mock_exec.return_value = mock_process

        # Test existing repository
        mock_process.returncode = 0
        assert await _check_repo_exists(url) is True

        # Test non-existing repository (404 response)
        mock_process.communicate.return_value = (b"HTTP/1.1 404 Not Found\n", b"")
        mock_process.returncode = 0
        assert await _check_repo_exists(url) is False

        # Test failed request
        mock_process.returncode = 1
        assert await _check_repo_exists(url) is False


@pytest.mark.asyncio
async def test_clone_repo_invalid_url() -> None:
    clone_config = CloneConfig(
        url="",
        local_path="/tmp/repo",
    )
    with pytest.raises(ValueError, match="The 'url' parameter is required."):
        await clone_repo(clone_config)


@pytest.mark.asyncio
async def test_clone_repo_invalid_local_path() -> None:
    clone_config = CloneConfig(
        url="https://github.com/user/repo",
        local_path="",
    )
    with pytest.raises(ValueError, match="The 'local_path' parameter is required."):
        await clone_repo(clone_config)


@pytest.mark.asyncio
async def test_clone_repo_with_custom_branch() -> None:
    clone_config = CloneConfig(
        url="https://github.com/user/repo",
        local_path="/tmp/repo",
        branch="feature-branch",
    )
    with patch("gitingest.clone._check_repo_exists", return_value=True):
        with patch("gitingest.clone._run_git_command", new_callable=AsyncMock) as mock_exec:
            await clone_repo(clone_config)
            mock_exec.assert_called_once_with(
                "git",
                "clone",
                "--depth=1",
                "--single-branch",
                "--branch",
                "feature-branch",
                clone_config.url,
                clone_config.local_path,
            )


@pytest.mark.asyncio
async def test_git_command_failure() -> None:
    clone_config = CloneConfig(
        url="https://github.com/user/repo",
        local_path="/tmp/repo",
    )
    with patch("gitingest.clone._check_repo_exists", return_value=True):
        with patch("gitingest.clone._run_git_command", side_effect=RuntimeError("Git command failed")):
            with pytest.raises(RuntimeError, match="Git command failed"):
                await clone_repo(clone_config)


@pytest.mark.asyncio
async def test_clone_repo_default_shallow_clone() -> None:
    clone_config = CloneConfig(
        url="https://github.com/user/repo",
        local_path="/tmp/repo",
    )
    with patch("gitingest.clone._check_repo_exists", return_value=True):
        with patch("gitingest.clone._run_git_command", new_callable=AsyncMock) as mock_exec:
            await clone_repo(clone_config)
            mock_exec.assert_called_once_with(
                "git", "clone", "--depth=1", "--single-branch", clone_config.url, clone_config.local_path
            )


@pytest.mark.asyncio
async def test_clone_repo_commit_without_branch() -> None:
    clone_config = CloneConfig(
        url="https://github.com/user/repo",
        local_path="/tmp/repo",
        commit="a" * 40,  # Simulating a valid commit hash
    )
    with patch("gitingest.clone._check_repo_exists", return_value=True):
        with patch("gitingest.clone._run_git_command", new_callable=AsyncMock) as mock_exec:
            await clone_repo(clone_config)
            assert mock_exec.call_count == 2  # Clone and checkout calls
            mock_exec.assert_any_call("git", "clone", "--single-branch", clone_config.url, clone_config.local_path)
            mock_exec.assert_any_call("git", "-C", clone_config.local_path, "checkout", clone_config.commit)


@pytest.mark.asyncio
async def test_check_repo_exists_with_redirect() -> None:
    url = "https://github.com/user/repo"
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"HTTP/1.1 302 Found\n", b"")
        mock_process.returncode = 0  # Simulate successful request
        mock_exec.return_value = mock_process

        assert await _check_repo_exists(url)
