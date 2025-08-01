"""Test that ``gitingest.ingest()`` emits a concise, 5-or-6-line summary."""

import re
from pathlib import Path

import pytest

from gitingest import ingest

REPO = "pallets/flask"

PATH_CASES = [
    ("tree", "/examples/celery"),
    ("blob", "/examples/celery/make_celery.py"),
    ("blob", "/.gitignore"),
]

REF_CASES = [
    ("Branch", "main"),
    ("Branch", "stable"),
    ("Tag", "3.0.3"),
    ("Commit", "e9741288637e0d9abe95311247b4842a017f7d5c"),
]


@pytest.mark.parametrize(("path_type", "path"), PATH_CASES)
@pytest.mark.parametrize(("ref_type", "ref"), REF_CASES)
def test_ingest_summary(path_type: str, path: str, ref_type: str, ref: str) -> None:
    """Assert that ``gitingest.ingest()`` emits a concise, 5-or-6-line summary.

    - Non-'main” refs → 5 key/value pairs + blank line (6 total).
    - 'main” branch   → ref line omitted (5 total).
    - Required keys:
        - Repository
        - ``ref_type`` (absent on 'main”)
        - File│Subpath (chosen by ``path_type``)
        - Lines│Files analyzed (chosen by ``path_type``)
        - Estimated tokens (positive integer)

    Any missing key, wrong value, or incorrect line count should fail.

    Parameters
    ----------
    path_type : {"tree", "blob"}
        GitHub object type under test.
    path : str
        The repository sub-path or file path to feed into the URL.
    ref_type : {"Branch", "Tag", "Commit"}
        Label expected on line 2 of the summary (absent if `ref` is "main").
    ref : str
        Actual branch name, tag, or commit hash.

    """
    is_main_branch = ref == "main"
    is_blob = path_type == "blob"
    expected_lines = _calculate_expected_lines(ref_type, is_main_branch=is_main_branch)
    expected_non_empty_lines = expected_lines - 1

    summary, _, _ = ingest(f"https://github.com/{REPO}/{path_type}/{ref}{path}")
    lines = summary.splitlines()
    parsed_lines = dict(line.split(": ", 1) for line in lines if ": " in line)

    assert parsed_lines["Repository"] == REPO

    if is_main_branch:
        # We omit the 'Branch' line for 'main' branches.
        assert ref_type not in parsed_lines
    else:
        assert parsed_lines[ref_type] == ref

    if is_blob:
        assert parsed_lines["File"] == Path(path).name
        assert "Lines" in parsed_lines
    else:  # 'tree'
        assert parsed_lines["Subpath"] == path
        assert "Files analyzed" in parsed_lines

    token_match = re.search(r"\d+", parsed_lines["Estimated tokens"])
    assert token_match, "'Estimated tokens' should contain a number"
    assert int(token_match.group()) > 0

    assert len(lines) == expected_lines
    assert len(parsed_lines) == expected_non_empty_lines


def _calculate_expected_lines(ref_type: str, *, is_main_branch: bool) -> int:
    """Calculate the expected number of lines in the summary.

    The total number of lines depends on the following:
    - Commit type does not include the 'Branch'/'Tag' line, reducing the count by 1.
    - The "main" branch omits the 'Branch' line, reducing the count by 1.

    Parameters
    ----------
    ref_type : str
        The type of reference, e.g., "Branch", "Tag", or "Commit".
    is_main_branch : bool
        True if the reference is the "main" branch, False otherwise.

    Returns
    -------
    int
        The expected number of lines in the summary.

    """
    base_lines = 7
    if is_main_branch:
        base_lines -= 1
    if ref_type == "Commit":
        base_lines -= 1
    return base_lines
