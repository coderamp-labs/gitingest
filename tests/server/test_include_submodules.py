import pytest
from pytest_mock import MockerFixture
from unittest.mock import AsyncMock

from gitingest.schemas.ingestion import IngestionQuery
from src.server.models import PatternType


@pytest.mark.asyncio
async def test_process_query_forwards_include_submodules(mocker: MockerFixture) -> None:
    query = IngestionQuery(
        host="github.com",
        user_name="octocat",
        repo_name="Hello-World",
        local_path="/tmp/gitingest/test-include-submodules",
        url="https://github.com/octocat/Hello-World",
        slug="octocat/Hello-World",
        id="00000000-0000-0000-0000-000000000001",
        branch="main",
        commit="deadbeef",
    )

    mocker.patch("src.server.query_processor.parse_remote_repo", new_callable=AsyncMock, return_value=query)
    clone_repo = mocker.patch("src.server.query_processor.clone_repo", new_callable=AsyncMock)
    mocker.patch("src.server.query_processor.ingest_query", return_value=("summary", "tree", "content"))
    mocker.patch("src.server.query_processor._store_digest_content")
    mocker.patch("src.server.query_processor._cleanup_repository")
    mocker.patch("src.server.query_processor._print_success")

    from src.server.query_processor import process_query

    await process_query(
        input_text="https://github.com/octocat/Hello-World",
        max_file_size=243,
        pattern_type=PatternType.EXCLUDE,
        pattern="",
        token=None,
        include_submodules=True,
    )

    assert clone_repo.call_count == 1
    passed_config = clone_repo.call_args.args[0]
    assert getattr(passed_config, "include_submodules") is True
