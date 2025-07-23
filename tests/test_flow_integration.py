"""Integration tests covering core functionalities, edge cases, and concurrency handling."""

import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Generator

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from src.server.main import app

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "src" / "templates"


@pytest.fixture(scope="module")
def test_client() -> Generator[TestClient, None, None]:
    """Create a test client fixture."""
    with TestClient(app) as client_instance:
        client_instance.headers.update({"Host": "localhost"})
        yield client_instance


@pytest.fixture(autouse=True)
def mock_static_files(mocker: MockerFixture) -> None:
    """Mock the static file mount to avoid directory errors."""
    mock_static = mocker.patch("src.server.main.StaticFiles", autospec=True)
    mock_static.return_value = None
    return mock_static


@pytest.fixture(scope="module", autouse=True)
def cleanup_tmp_dir() -> Generator[None, None, None]:
    """Remove ``/tmp/gitingest`` after this test-module is done."""
    yield  # run tests
    temp_dir = Path("/tmp/gitingest")
    if temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
        except PermissionError as exc:
            print(f"Error cleaning up {temp_dir}: {exc}")


@pytest.mark.asyncio
async def test_remote_repository_analysis(request: pytest.FixtureRequest) -> None:
    """Test the complete flow of analyzing a remote repository."""
    client = request.getfixturevalue("test_client")
    form_data = {
        "input_text": "https://github.com/microsoft/vscode",
        "max_file_size": "243",
        "pattern_type": "exclude",
        "pattern": "",
        "token": "",
    }

    response = client.post("/api/ingest", json=form_data)
    assert response.status_code == status.HTTP_200_OK, f"Form submission failed: {response.text}"

    # Check that response is JSON
    response_data = response.json()
    assert "content" in response_data
    assert response_data["content"]
    assert "repo_url" in response_data
    assert "summary" in response_data
    assert "tree" in response_data
    assert "content" in response_data


@pytest.mark.asyncio
async def test_invalid_repository_url(request: pytest.FixtureRequest) -> None:
    """Test handling of an invalid repository URL."""
    client = request.getfixturevalue("test_client")
    form_data = {
        "input_text": "https://github.com/nonexistent/repo",
        "max_file_size": "243",
        "pattern_type": "exclude",
        "pattern": "",
        "token": "",
    }

    response = client.post("/api/ingest", json=form_data)
    # Should return 400 for invalid repository
    assert response.status_code == status.HTTP_400_BAD_REQUEST, f"Request failed: {response.text}"

    # Check that response is JSON error
    response_data = response.json()
    assert "error" in response_data


@pytest.mark.asyncio
async def test_large_repository(request: pytest.FixtureRequest) -> None:
    """Simulate analysis of a large repository with nested folders and many files."""
    client = request.getfixturevalue("test_client")
    form_data = {
        "input_text": "https://github.com/microsoft/vscode",
        "max_file_size": "100",  # Lower this to force skipping large files
        "pattern_type": "exclude",
        "pattern": "",
        "token": "",
    }

    response = client.post("/api/ingest", json=form_data)
    assert response.status_code == status.HTTP_200_OK, f"Request failed: {response.text}"

    response_data = response.json()
    if response.status_code == status.HTTP_200_OK:
        assert "content" in response_data
        assert isinstance(response_data["content"], str)
    else:
        assert "error" in response_data


@pytest.mark.asyncio
async def test_concurrent_requests(request: pytest.FixtureRequest) -> None:
    """Test handling of multiple concurrent requests."""
    client = request.getfixturevalue("test_client")

    def make_request() -> None:
        form_data = {
            "input_text": "https://github.com/microsoft/vscode",
            "max_file_size": "243",
            "pattern_type": "exclude",
            "pattern": "",
            "token": "",
        }
        response = client.post("/api/ingest", json=form_data)
        assert response.status_code == status.HTTP_200_OK, f"Request failed: {response.text}"

        response_data = response.json()
        if response.status_code == status.HTTP_200_OK:
            assert "content" in response_data
            assert response_data["content"]
        else:
            assert "error" in response_data

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request) for _ in range(5)]
        for future in futures:
            future.result()


@pytest.mark.asyncio
async def test_large_file_handling(request: pytest.FixtureRequest) -> None:
    """Test handling of repositories with large files."""
    client = request.getfixturevalue("test_client")
    form_data = {
        "input_text": "https://github.com/microsoft/vscode",
        "max_file_size": "1",
        "pattern_type": "exclude",
        "pattern": "",
        "token": "",
    }

    response = client.post("/api/ingest", json=form_data)
    assert response.status_code == status.HTTP_200_OK, f"Request failed: {response.text}"

    response_data = response.json()
    if response.status_code == status.HTTP_200_OK:
        assert "content" in response_data
        assert response_data["content"]
    else:
        assert "error" in response_data


@pytest.mark.asyncio
async def test_repository_with_patterns(request: pytest.FixtureRequest) -> None:
    """Test repository analysis with include/exclude patterns."""
    client = request.getfixturevalue("test_client")
    form_data = {
        "input_text": "https://github.com/microsoft/vscode",
        "max_file_size": "243",
        "pattern_type": "include",
        "pattern": "*.md",
        "token": "",
    }

    response = client.post("/api/ingest", json=form_data)
    assert response.status_code == status.HTTP_200_OK, f"Request failed: {response.text}"

    response_data = response.json()
    if response.status_code == status.HTTP_200_OK:
        assert "content" in response_data
        assert isinstance(response_data["content"], str)

        assert "repo_url" in response_data
        assert response_data["repo_url"].startswith("https://github.com/")

        assert "summary" in response_data
        assert isinstance(response_data["summary"], str)
        assert "microsoft/vscode" in response_data["summary"].lower()

        assert "tree" in response_data
        assert isinstance(response_data["tree"], str)
        assert "microsoft-vscode" in response_data["tree"].lower()

        assert "pattern_type" in response_data
        assert response_data["pattern_type"] == "include"

        assert "pattern" in response_data
        assert response_data["pattern"] == "*.md"
    else:
        assert "error" in response_data
        assert isinstance(response_data["error"], str)
        assert response_data["error"]  # not empty


@pytest.mark.asyncio
async def test_missing_required_fields(request: pytest.FixtureRequest) -> None:
    """Test API response when required fields are missing."""
    client = request.getfixturevalue("test_client")
    form_data = {
        "max_file_size": "243",
        "pattern_type": "exclude",
        "pattern": "",
        "token": "",
    }
    response = client.post("/api/ingest", json=form_data)
    assert response.status_code in (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        status.HTTP_429_TOO_MANY_REQUESTS,
        status.HTTP_200_OK,
    )

    form_data = {
        "input_text": "https://github.com/microsoft/vscode",
        "max_file_size": "243",
        "pattern": "",
        "token": "",
    }
    response = client.post("/api/ingest", json=form_data)
    assert response.status_code in (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        status.HTTP_429_TOO_MANY_REQUESTS,
        status.HTTP_200_OK,
    )


@pytest.mark.asyncio
async def test_invalid_field_types(request: pytest.FixtureRequest) -> None:
    """Test API response when fields have invalid types."""
    client = request.getfixturevalue("test_client")

    form_data = {
        "input_text": 12345,
        "max_file_size": "243",
        "pattern_type": "exclude",
        "pattern": "",
        "token": "",
    }
    response = client.post("/api/ingest", json=form_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    form_data = {
        "input_text": "https://github.com/microsoft/vscode",
        "max_file_size": "243",
        "pattern_type": "exclude",
        "pattern": ["*.md"],
        "token": "",
    }
    response = client.post("/api/ingest", json=form_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_unsupported_pattern_type(request: pytest.FixtureRequest) -> None:
    """Test API response for unsupported pattern_type."""
    client = request.getfixturevalue("test_client")
    form_data = {
        "input_text": "https://github.com/microsoft/vscode",
        "max_file_size": "243",
        "pattern_type": "invalid_type",
        "pattern": "*.md",
        "token": "",
    }
    response = client.post("/api/ingest", json=form_data)
    assert response.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)
    response_data = response.json()
    assert "error" in response_data or "detail" in response_data


@pytest.mark.asyncio
async def test_invalid_token(request: pytest.FixtureRequest) -> None:
    """Test API response for an invalid or expired token."""
    client = request.getfixturevalue("test_client")
    form_data = {
        "input_text": "https://github.com/microsoft/vscode",
        "max_file_size": "243",
        "pattern_type": "exclude",
        "pattern": "",
        "token": "invalid_token_1234567890",
    }
    response = client.post("/api/ingest", json=form_data)
    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_429_TOO_MANY_REQUESTS,
    )
    response_data = response.json()
    assert "error" in response_data or "detail" in response_data
