"""Tests for the way symlinks are reported.

``gitingest`` deliberately does not resolve symlinks: it records the link itself and prints where it
points. These tests cover the second half of that promise. The target has to be reported as it is
stored on disk, because that is the part which says whether the link stays inside the ingested tree.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from gitingest.ingestion import ingest_query
from gitingest.schemas import FileSystemNode, FileSystemNodeType

if TYPE_CHECKING:
    from gitingest.query_parser import IngestionQuery

OUTSIDE_CONTENT = "content that lives outside the ingested tree"


@pytest.fixture
def symlink_repo(tmp_path: Path) -> Path:
    """Create a repository with symlinks pointing outside and inside the tree.

    The structure is::

        tmp_path/
        ├── outside/
        │   └── secret.txt
        └── test_repo/
            ├── file.txt
            └── links/
                ├── absolute -> <tmp_path>/outside/secret.txt
                ├── relative -> ../../outside/secret.txt
                └── inside   -> ../file.txt

    Parameters
    ----------
    tmp_path : Path
        The temporary directory path provided by the ``tmp_path`` fixture.

    Returns
    -------
    Path
        The path to the created ``test_repo`` directory.

    """
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text(OUTSIDE_CONTENT)

    test_dir = tmp_path / "test_repo"
    test_dir.mkdir()
    (test_dir / "file.txt").write_text("Hello World")

    links = test_dir / "links"
    links.mkdir()
    try:
        # Creating a symlink needs a privilege that Windows runners do not always have.
        (links / "absolute").symlink_to(outside / "secret.txt")
        (links / "relative").symlink_to(Path("../../outside/secret.txt"))
        (links / "inside").symlink_to(Path("../file.txt"))
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"This platform cannot create symlinks: {exc}")

    return test_dir


def _symlink_target(text: str, path_str: str) -> str:
    """Return the target reported for a given symlink.

    Parameters
    ----------
    text : str
        The ingested content or directory structure to search.
    path_str : str
        The path of the symlink, as it appears before the arrow.

    Returns
    -------
    str
        The text reported after the ``->`` marker.

    Raises
    ------
    AssertionError
        If no line reports that symlink.

    """
    marker = f"{path_str} -> "
    for line in text.splitlines():
        if marker in line:
            return line.split(marker, 1)[1]

    msg = f"No symlink line for {path_str!r} in:\n{text}"
    raise AssertionError(msg)


def test_symlink_outside_tree_reports_the_whole_target(symlink_repo: Path, sample_query: IngestionQuery) -> None:
    """Test that an absolute symlink leaving the tree reports its whole target.

    Given a symlink pointing at an absolute path outside the repository:
    When ``ingest_query`` is invoked,
    Then the reported target should be the full path, not just its file name.
    """
    sample_query.local_path = symlink_repo
    sample_query.subpath = "/"
    sample_query.type = None

    _, _, content = ingest_query(sample_query)

    target = _symlink_target(content, "links/absolute")

    assert target.endswith("outside/secret.txt")
    assert target != "secret.txt"


def test_relative_symlink_keeps_the_parent_steps(symlink_repo: Path, sample_query: IngestionQuery) -> None:
    """Test that a relative symlink walking out of the tree keeps its ``..`` steps.

    Given a symlink whose target is ``../../outside/secret.txt``:
    When ``ingest_query`` is invoked,
    Then the reported target should still start with the parent steps that leave the tree.
    """
    sample_query.local_path = symlink_repo
    sample_query.subpath = "/"
    sample_query.type = None

    _, _, content = ingest_query(sample_query)

    target = _symlink_target(content, "links/relative")

    assert target.startswith("../../")
    assert target.endswith("outside/secret.txt")


def test_symlink_target_is_shown_in_the_directory_structure(
    symlink_repo: Path,
    sample_query: IngestionQuery,
) -> None:
    """Test that the directory structure reports the target too.

    Given a repository containing symlinks:
    When ``ingest_query`` is invoked,
    Then the tree should show the target of a link that stays inside the tree.
    """
    sample_query.local_path = symlink_repo
    sample_query.subpath = "/"
    sample_query.type = None

    _, structure, _ = ingest_query(sample_query)

    assert _symlink_target(structure, "inside") == "../file.txt"


def test_symlink_content_is_not_inlined(symlink_repo: Path, sample_query: IngestionQuery) -> None:
    """Test that the content behind a symlink is not pulled into the output.

    Given a symlink pointing at a file outside the repository:
    When ``ingest_query`` is invoked,
    Then the content of that file should not appear in the output.
    """
    sample_query.local_path = symlink_repo
    sample_query.subpath = "/"
    sample_query.type = None

    _, _, content = ingest_query(sample_query)

    assert OUTSIDE_CONTENT not in content


def test_symlink_target_of_a_regular_file_raises(symlink_repo: Path) -> None:
    """Test that asking a non-symlink node for a symlink target is an error.

    Given a node describing a regular file:
    When ``symlink_target`` is read,
    Then a ``ValueError`` should be raised.
    """
    node = FileSystemNode(
        name="file.txt",
        type=FileSystemNodeType.FILE,
        path_str="file.txt",
        path=symlink_repo / "file.txt",
    )

    with pytest.raises(ValueError, match="non-symlink"):
        _ = node.symlink_target
