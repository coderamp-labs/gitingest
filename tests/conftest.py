"""Fixtures for tests.

This file provides shared fixtures for creating sample queries, a temporary directory structure, and a helper function
to write ``.ipynb`` notebooks for testing notebook utilities.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from gitingest.query_parser import IngestionQuery

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

WriteNotebookFunc = Callable[[str, Dict[str, Any]], Path]

DEMO_URL = "https://github.com/user/repo"
LOCAL_REPO_PATH = "/tmp/repo"
DEMO_COMMIT = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"


def get_ensure_git_installed_call_count() -> int:
    """Get the number of calls made by ensure_git_installed based on platform.

    On Windows, ensure_git_installed makes 2 calls:
    1. git --version
    2. git config core.longpaths

    On other platforms, it makes 1 call:
    1. git --version

    Returns
    -------
    int
        The number of calls made by ensure_git_installed

    """
    return 2 if sys.platform == "win32" else 1


@pytest.fixture
def sample_query() -> IngestionQuery:
    """Provide a default ``IngestionQuery`` object for use in tests.

    This fixture returns a ``IngestionQuery`` pre-populated with typical fields and some default ignore patterns.

    Returns
    -------
    IngestionQuery
        The sample ``IngestionQuery`` object.

    """
    return IngestionQuery(
        user_name="test_user",
        repo_name="test_repo",
        local_path=Path("/tmp/test_repo").resolve(),
        slug="test_user/test_repo",
        id=uuid.uuid4(),
        branch="main",
        max_file_size=1_000_000,
        ignore_patterns={"*.pyc", "__pycache__", ".git"},
    )


@pytest.fixture
def temp_directory(tmp_path: Path) -> Path:
    """Create a temporary directory structure for testing repository scanning.

    The structure includes:
    test_repo/
    ├── file1.txt
    ├── file2.py
    ├── src/
    │   ├── subfile1.txt
    │   ├── subfile2.py
    │   └── subdir/
    │       ├── file_subdir.txt
    │       └── file_subdir.py
    ├── dir1/
    │   └── file_dir1.txt
    └── dir2/
        └── file_dir2.txt

    Parameters
    ----------
    tmp_path : Path
        The temporary directory path provided by the ``tmp_path`` fixture.

    Returns
    -------
    Path
        The path to the created ``test_repo`` directory.

    """
    test_dir = tmp_path / "test_repo"
    test_dir.mkdir()

    # Root files
    (test_dir / "file1.txt").write_text("Hello World")
    (test_dir / "file2.py").write_text("print('Hello')")

    # src directory and its files
    src_dir = test_dir / "src"
    src_dir.mkdir()
    (src_dir / "subfile1.txt").write_text("Hello from src")
    (src_dir / "subfile2.py").write_text("print('Hello from src')")

    # src/subdir and its files
    subdir = src_dir / "subdir"
    subdir.mkdir()
    (subdir / "file_subdir.txt").write_text("Hello from subdir")
    (subdir / "file_subdir.py").write_text("print('Hello from subdir')")

    # dir1 and its file
    dir1 = test_dir / "dir1"
    dir1.mkdir()
    (dir1 / "file_dir1.txt").write_text("Hello from dir1")

    # dir2 and its file
    dir2 = test_dir / "dir2"
    dir2.mkdir()
    (dir2 / "file_dir2.txt").write_text("Hello from dir2")

    return test_dir


@pytest.fixture
def write_notebook(tmp_path: Path) -> WriteNotebookFunc:
    """Provide a helper function to write a ``.ipynb`` notebook file with the given content.

    Parameters
    ----------
    tmp_path : Path
        The temporary directory path provided by the ``tmp_path`` fixture.

    Returns
    -------
    WriteNotebookFunc
        A callable that accepts a filename and a dictionary (representing JSON notebook data), writes it to a
        ``.ipynb`` file, and returns the path to the file.

    """

    def _write_notebook(name: str, content: dict[str, Any]) -> Path:
        notebook_path = tmp_path / name
        with notebook_path.open(mode="w", encoding="utf-8") as f:
            json.dump(content, f)
        return notebook_path

    return _write_notebook


@pytest.fixture
def stub_resolve_sha(mocker: MockerFixture) -> dict[str, AsyncMock]:
    """Patch *both* async helpers that hit the network.

    Include this fixture *only* in tests that should stay offline.
    """
    head_mock = mocker.patch(
        "gitingest.utils.query_parser_utils._resolve_ref_to_sha",
        new_callable=mocker.AsyncMock,
        return_value=DEMO_COMMIT,
    )
    ref_mock = mocker.patch(
        "gitingest.utils.git_utils._resolve_ref_to_sha",
        new_callable=mocker.AsyncMock,
        return_value=DEMO_COMMIT,
    )
    # return whichever you want to assert on; here we return the dict
    return {"head": head_mock, "ref": ref_mock}


@pytest.fixture
def stub_branches(mocker: MockerFixture) -> Callable[[list[str]], None]:
    """Return a function that stubs git branch discovery to *branches*."""

    def _factory(branches: list[str]) -> None:
        # Patch the GitPython fetch function
        mocker.patch(
            "gitingest.utils.git_utils.fetch_remote_branches_or_tags",
            new_callable=AsyncMock,
            return_value=branches,
        )

        # Patch GitPython's ls_remote method to return the mocked output
        ls_remote_output = "\n".join(f"{DEMO_COMMIT[:12]}{i:02d}\trefs/heads/{b}" for i, b in enumerate(branches))
        mock_git_cmd = mocker.patch("git.Git")
        mock_git_cmd.return_value.ls_remote.return_value = ls_remote_output

        # Also patch the git module imports in our utils
        mocker.patch("gitingest.utils.git_utils.git.Git", return_value=mock_git_cmd.return_value)

    return _factory


@pytest.fixture
def repo_exists_true(mocker: MockerFixture) -> AsyncMock:
    """Patch ``gitingest.clone.check_repo_exists`` to always return ``True``."""
    return mocker.patch("gitingest.clone.check_repo_exists", return_value=True)


@pytest.fixture
def run_command_mock(mocker: MockerFixture) -> AsyncMock:
    """Patch ``gitingest.clone.run_command`` with an ``AsyncMock``.

    The mocked function returns a dummy process whose ``communicate`` method yields generic
    ``stdout`` / ``stderr`` bytes. Tests can still access / tweak the mock via the fixture argument.
    """
    mock = AsyncMock(side_effect=_fake_run_command)
    mocker.patch("gitingest.utils.git_utils.run_command", mock)

    # Mock GitPython components
    _setup_gitpython_mocks(mocker)

    return mock


@pytest.fixture
def gitpython_mocks(mocker: MockerFixture) -> dict[str, MagicMock]:
    """Provide comprehensive GitPython mocks for testing."""
    return _setup_gitpython_mocks(mocker)


def _setup_gitpython_mocks(mocker: MockerFixture) -> dict[str, MagicMock]:
    """Set up comprehensive GitPython mocks."""
    # Mock git.Git class
    mock_git_cmd = MagicMock()
    mock_git_cmd.version.return_value = "git version 2.34.1"
    mock_git_cmd.config.return_value = "true"
    mock_git_cmd.execute.return_value = f"{DEMO_COMMIT}\trefs/heads/main\n"
    mock_git_cmd.ls_remote.return_value = f"{DEMO_COMMIT}\trefs/heads/main\n"
    mock_git_cmd.clone.return_value = ""

    # Mock git.Repo class
    mock_repo = MagicMock()
    mock_repo.git = MagicMock()
    mock_repo.git.fetch = MagicMock()
    mock_repo.git.checkout = MagicMock()
    mock_repo.git.submodule = MagicMock()
    mock_repo.git.execute = MagicMock()
    mock_repo.git.config = MagicMock()
    mock_repo.git.sparse_checkout = MagicMock()

    # Mock git.Repo.clone_from
    mock_clone_from = MagicMock(return_value=mock_repo)

    git_git_mock = mocker.patch("git.Git", return_value=mock_git_cmd)
    git_repo_mock = mocker.patch("git.Repo", return_value=mock_repo)
    mocker.patch("git.Repo.clone_from", mock_clone_from)

    # Patch imports in our modules
    mocker.patch("gitingest.utils.git_utils.git.Git", return_value=mock_git_cmd)
    mocker.patch("gitingest.utils.git_utils.git.Repo", return_value=mock_repo)
    mocker.patch("gitingest.clone.git.Git", return_value=mock_git_cmd)
    mocker.patch("gitingest.clone.git.Repo", return_value=mock_repo)
    mocker.patch("gitingest.clone.git.Repo.clone_from", mock_clone_from)

    return {
        "git_cmd": mock_git_cmd,
        "repo": mock_repo,
        "clone_from": mock_clone_from,
        "git_git_mock": git_git_mock,
        "git_repo_mock": git_repo_mock,
    }


async def _fake_run_command(*args: str) -> tuple[bytes, bytes]:
    if "ls-remote" in args:
        # single match: <sha> <tab>refs/heads/main
        return (f"{DEMO_COMMIT}\trefs/heads/main\n".encode(), b"")
    return (b"output", b"error")
