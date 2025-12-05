"""Command-line interface (CLI) for Gitingest."""

# pylint: disable=no-value-for-parameter
from __future__ import annotations

import asyncio
from typing import TypedDict

import click
from typing_extensions import Unpack

from gitingest.config import MAX_FILE_SIZE, OUTPUT_FILE_NAME
from gitingest.entrypoint import ingest_async
from gitingest.extract import extract

# Import logging configuration first to intercept all logging
from gitingest.utils.logging_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)


class _CLIArgs(TypedDict):
    source: str
    max_size: int
    exclude_pattern: tuple[str, ...]
    include_pattern: tuple[str, ...]
    branch: str | None
    include_gitignored: bool
    include_submodules: bool
    token: str | None
    output: str | None


class DefaultGroup(click.Group):
    """A Click Group that invokes a default command if a subcommand is not found."""

    def parse_args(self, ctx, args):
        if args and args[0] in ["--help", "-h"]:
            return super().parse_args(ctx, args)

        if not args or args[0] not in self.commands:
            # Default to ingest command
            # Insert "ingest" as the first argument
            args = ["ingest"] + args
        
        return super().parse_args(ctx, args)


@click.group(cls=DefaultGroup)
def main() -> None:
    """Gitingest CLI tool.

    The default command is 'ingest', which analyzes a directory or repository.
    Use 'gitingest ingest --help' to see options for the default command.
    
    To extract files from a digest, use 'gitingest extract'.
    """
    pass


@main.command(name="ingest")
@click.argument("source", type=str, default=".")
@click.option(
    "--max-size",
    "-s",
    default=MAX_FILE_SIZE,
    show_default=True,
    help="Maximum file size to process in bytes",
)
@click.option("--exclude-pattern", "-e", multiple=True, help="Shell-style patterns to exclude.")
@click.option(
    "--include-pattern",
    "-i",
    multiple=True,
    help="Shell-style patterns to include.",
)
@click.option("--branch", "-b", default=None, help="Branch to clone and ingest")
@click.option(
    "--include-gitignored",
    is_flag=True,
    default=False,
    help="Include files matched by .gitignore and .gitingestignore",
)
@click.option(
    "--include-submodules",
    is_flag=True,
    help="Include repository's submodules in the analysis",
    default=False,
)
@click.option(
    "--token",
    "-t",
    envvar="GITHUB_TOKEN",
    default=None,
    help=(
        "GitHub personal access token (PAT) for accessing private repositories. "
        "If omitted, the CLI will look for the GITHUB_TOKEN environment variable."
    ),
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Output file path (default: digest.txt in current directory). Use '-' for stdout.",
)
def ingest_command(**cli_kwargs: Unpack[_CLIArgs]) -> None:
    """Run the CLI entry point to analyze a repo / directory and dump its contents.

    Parameters
    ----------
    **cli_kwargs : Unpack[_CLIArgs]
        A dictionary of keyword arguments forwarded to ``ingest_async``.

    Notes
    -----
    See ``ingest_async`` for a detailed description of each argument.

    Examples
    --------
    Basic usage:
        $ gitingest
        $ gitingest /path/to/repo
        $ gitingest https://github.com/user/repo

    Output to stdout:
        $ gitingest -o -
        $ gitingest https://github.com/user/repo --output -

    With filtering:
        $ gitingest -i "*.py" -e "*.log"
        $ gitingest --include-pattern "*.js" --exclude-pattern "node_modules/*"

    Private repositories:
        $ gitingest https://github.com/user/private-repo -t ghp_token
        $ GITHUB_TOKEN=ghp_token gitingest https://github.com/user/private-repo

    Include submodules:
        $ gitingest https://github.com/user/repo --include-submodules

    """
    asyncio.run(_async_main(**cli_kwargs))


@main.command(name="extract")
@click.argument("digest_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--output",
    "-o",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Output directory where files will be extracted.",
)
def extract_command(digest_file: str, output: str) -> None:
    """Extract files from a gitingest digest file.

    Parameters
    ----------
    digest_file : str
        Path to the digest file.
    output : str
        Directory where extracted files will be saved.

    Examples
    --------
    Extract files from digest.txt to the current directory:
        $ gitingest extract digest.txt

    Extract files to a specific output directory:
        $ gitingest extract digest.txt --output ./restored-project

    """
    try:
        extract(digest_file, output)
        click.echo(f"Successfully extracted files to '{output}'")
    except Exception as exc:
        click.echo(f"Error extracting files: {exc}", err=True)
        raise click.Abort from exc


async def _async_main(
    source: str,
    *,
    max_size: int = MAX_FILE_SIZE,
    exclude_pattern: tuple[str, ...] | None = None,
    include_pattern: tuple[str, ...] | None = None,
    branch: str | None = None,
    include_gitignored: bool = False,
    include_submodules: bool = False,
    token: str | None = None,
    output: str | None = None,
) -> None:
    """Analyze a directory or repository and create a text dump of its contents.

    This command scans the specified ``source`` (a local directory or Git repo),
    applies custom include and exclude patterns, and generates a text summary of
    the analysis.  The summary is written to an output file or printed to ``stdout``.

    Parameters
    ----------
    source : str
        A directory path or a Git repository URL.
    max_size : int
        Maximum file size in bytes to ingest (default: 10 MB).
    exclude_pattern : tuple[str, ...] | None
        Glob patterns for pruning the file set.
    include_pattern : tuple[str, ...] | None
        Glob patterns for including files in the output.
    branch : str | None
        Git branch to ingest. If ``None``, the repository's default branch is used.
    include_gitignored : bool
        If ``True``, also ingest files matched by ``.gitignore`` or ``.gitingestignore`` (default: ``False``).
    include_submodules : bool
        If ``True``, recursively include all Git submodules within the repository (default: ``False``).
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.
        Can also be set via the ``GITHUB_TOKEN`` environment variable.
    output : str | None
        The path where the output file will be written (default: ``digest.txt`` in current directory).
        Use ``"-"`` to write to ``stdout``.

    Raises
    ------
    click.Abort
        Raised if an error occurs during execution and the command must be aborted.

    """
    try:
        # Normalise pattern containers (the ingest layer expects sets)
        exclude_patterns = set(exclude_pattern) if exclude_pattern else set()
        include_patterns = set(include_pattern) if include_pattern else set()

        output_target = output if output is not None else OUTPUT_FILE_NAME

        if output_target == "-":
            click.echo("Analyzing source, preparing output for stdout...", err=True)
        else:
            click.echo(f"Analyzing source, output will be written to '{output_target}'...", err=True)

        summary, _, _ = await ingest_async(
            source,
            max_file_size=max_size,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            branch=branch,
            include_gitignored=include_gitignored,
            include_submodules=include_submodules,
            token=token,
            output=output_target,
        )
    except Exception as exc:
        # Convert any exception into Click.Abort so that exit status is non-zero
        click.echo(f"Error: {exc}", err=True)
        raise click.Abort from exc

    if output_target == "-":  # stdout
        click.echo("\n--- Summary ---", err=True)
        click.echo(summary, err=True)
        click.echo("--- End Summary ---", err=True)
        click.echo("Analysis complete! Output sent to stdout.", err=True)
    else:  # file
        click.echo(f"Analysis complete! Output written to: {output_target}")
        click.echo("\nSummary:")
        click.echo(summary)


if __name__ == "__main__":
    main()
