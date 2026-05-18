"""Tests for the Gitingest CLI."""

from __future__ import annotations

from inspect import signature
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from gitingest.__main__ import main
from gitingest.config import MAX_FILE_SIZE, OUTPUT_FILE_NAME
from gitingest.schemas.filesystem import SEPARATOR


@pytest.mark.parametrize(
    ("cli_args", "expect_file"),
    [
        pytest.param(["./"], True, id="default-options"),
        pytest.param(
            [
                "./",
                "--output",
                str(OUTPUT_FILE_NAME),
                "--max-size",
                str(MAX_FILE_SIZE),
                "--exclude-pattern",
                "tests/",
                "--include-pattern",
                "src/",
                "--include-submodules",
            ],
            True,
            id="custom-options",
        ),
    ],
)
def test_cli_writes_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    cli_args: list[str],
    expect_file: bool,
) -> None:
    """Run the CLI and verify that the SARIF file is created (or not)."""
    expectes_exit_code = 0
    # Work inside an isolated temp directory
    monkeypatch.chdir(tmp_path)

    result = _invoke_isolated_cli_runner(cli_args)

    assert result.exit_code == expectes_exit_code, result.stderr

    # Summary line should be on STDOUT
    stdout_lines = result.stdout.splitlines()
    assert f"Analysis complete! Output written to: {OUTPUT_FILE_NAME}" in stdout_lines

    # File side-effect
    sarif_file = tmp_path / OUTPUT_FILE_NAME
    assert sarif_file.exists() is expect_file, f"{OUTPUT_FILE_NAME} existence did not match expectation"


def test_cli_with_stdout_output() -> None:
    """Test CLI invocation with output directed to STDOUT."""
    output_file = Path(OUTPUT_FILE_NAME)
    # Clean up any existing digest.txt file before test
    if output_file.exists():
        output_file.unlink()

    try:
        result = _invoke_isolated_cli_runner(["./", "--output", "-", "--exclude-pattern", "tests/"])

        # ─── core expectations (stdout) ────────────────────────────────────-
        assert result.exit_code == 0, f"CLI exited with code {result.exit_code}, stderr: {result.stderr}"
        assert "---" in result.stdout, "Expected file separator '---' not found in STDOUT"
        assert "src/gitingest/__main__.py" in result.stdout, (
            "Expected content (e.g., src/gitingest/__main__.py) not found in STDOUT"
        )
        assert not output_file.exists(), f"Output file {output_file} was unexpectedly created."

        # ─── the summary must *not* pollute STDOUT, must appear on STDERR ───
        summary = "Analysis complete! Output sent to stdout."
        stdout_lines = result.stdout.splitlines()
        stderr_lines = result.stderr.splitlines()
        assert summary not in stdout_lines, "Unexpected summary message found in STDOUT"
        assert summary in stderr_lines, "Expected summary message not found in STDERR"
        assert f"Output written to: {output_file.name}" not in stderr_lines
    finally:
        # Clean up any digest.txt file that might have been created during test
        if output_file.exists():
            output_file.unlink()


def _invoke_isolated_cli_runner(args: list[str]) -> Result:
    """Return a ``CliRunner`` that keeps ``stderr`` separate on Click 8.0-8.1."""
    kwargs = {}
    if "mix_stderr" in signature(CliRunner.__init__).parameters:
        kwargs["mix_stderr"] = False  # Click 8.0-8.1
    runner = CliRunner(**kwargs)
    return runner.invoke(main, args)


def test_cli_restore_mode(tmp_path: Path) -> None:
    """Restore mode should recreate files from a digest."""
    digest_path = tmp_path / OUTPUT_FILE_NAME
    digest_path.write_text(
        (
            f"{SEPARATOR}\n"
            "FILE: src/hello.py\n"
            f"{SEPARATOR}\n"
            "print('hello')\n\n"
        ),
        encoding="utf-8",
    )

    restore_target = tmp_path / "restored"
    result = _invoke_isolated_cli_runner(
        [str(digest_path), "--restore", "--restore-dir", str(restore_target)],
    )

    assert result.exit_code == 0, result.stderr
    assert "Recreated 1 files, 1 directories, and 0 symlinks" in result.stdout
    assert (restore_target / "src" / "hello.py").read_text(encoding="utf-8") == "print('hello')"
