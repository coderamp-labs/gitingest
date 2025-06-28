"""Process a query by parsing input, cloning a repository, and generating a summary."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, cast

from gitingest.clone import clone_repo
from gitingest.ingestion import ingest_query
from gitingest.query_parser import IngestionQuery, parse_query
from server.server_config import (
    DEFAULT_FILE_SIZE_KB,
    EXAMPLE_REPOS,
    MAX_DISPLAY_SIZE,
    templates,
)
from server.server_utils import Colors, log_slider_to_size

if TYPE_CHECKING:
    from fastapi import Request
    from starlette.templating import _TemplateResponse


async def process_query(
    request: Request,
    *,
    input_text: str,
    slider_position: int,
    pattern_type: str = "exclude",
    pattern: str = "",
    is_index: bool = False,
    token: str | None = None,
) -> _TemplateResponse:
    """Process a query by parsing input, cloning a repository, and generating a summary.

    Handle user input, process Git repository data, and prepare
    a response for rendering a template with the processed results or an error message.

    Parameters
    ----------
    request : Request
        The HTTP request object.
    input_text : str
        Input text provided by the user, typically a Git repository URL or slug.
    slider_position : int
        Position of the slider, representing the maximum file size in the query.
    pattern_type : str
        Type of pattern to use (either "include" or "exclude") (default: ``"exclude"``).
    pattern : str
        Pattern to include or exclude in the query, depending on the pattern type.
    is_index : bool
        Flag indicating whether the request is for the index page (default: ``False``).
    token : str | None
        GitHub personal access token (PAT) for accessing private repositories.

    Returns
    -------
    _TemplateResponse
        Rendered template response containing the processed results or an error message.

    Raises
    ------
    ValueError
        If an invalid pattern type is provided.

    """
    if pattern_type == "include":
        include_patterns = pattern
        exclude_patterns = None
    elif pattern_type == "exclude":
        exclude_patterns = pattern
        include_patterns = None
    else:
        msg = f"Invalid pattern type: {pattern_type}"
        raise ValueError(msg)

    template = "index.jinja" if is_index else "git.jinja"
    template_response = partial(templates.TemplateResponse, name=template)
    max_file_size = log_slider_to_size(slider_position)

    context = {
        "request": request,
        "repo_url": input_text,
        "examples": EXAMPLE_REPOS if is_index else [],
        "default_file_size": slider_position,
        "pattern_type": pattern_type,
        "pattern": pattern,
        "token": token,
    }

    query: IngestionQuery | None = None

    try:
        query = await parse_query(
            source=input_text,
            max_file_size=max_file_size,
            from_web=True,
            include_patterns=include_patterns,
            ignore_patterns=exclude_patterns,
            token=token,
        )
        query.ensure_url()

        # Sets the "<user>/<repo>" for the page title
        context["short_repo_url"] = f"{query.user_name}/{query.repo_name}"

        clone_config = query.extract_clone_config()
        await clone_repo(clone_config, token=token)

        summary, tree, content = ingest_query(query)

        local_txt_file = Path(clone_config.local_path).with_suffix(".txt")

        with local_txt_file.open("w", encoding="utf-8") as f:
            f.write(tree + "\n" + content)

    except Exception as exc:
        if query and query.url:
            _print_error(query.url, exc, max_file_size, pattern_type, pattern)
        else:
            print(f"{Colors.BROWN}WARN{Colors.END}: {Colors.RED}<-  {Colors.END}", end="")
            print(f"{Colors.RED}{exc}{Colors.END}")

        context["error_message"] = f"Error: {exc}"
        if "405" in str(exc):
            context["error_message"] = (
                "Repository not found. Please make sure it is public (private repositories will be supported soon)"
            )
        return template_response(context=context)

    if len(content) > MAX_DISPLAY_SIZE:
        content = (
            f"(Files content cropped to {int(MAX_DISPLAY_SIZE / 1_000)}k characters, "
            "download full ingest to see more)\n" + content[:MAX_DISPLAY_SIZE]
        )

    query.ensure_url()
    query.url = cast("str", query.url)

    _print_success(
        url=query.url,
        max_file_size=max_file_size,
        pattern_type=pattern_type,
        pattern=pattern,
        summary=summary,
    )

    context.update(
        {
            "result": True,
            "summary": summary,
            "tree": tree,
            "content": content,
            "ingest_id": query.id,
        },
    )

    return template_response(context=context)


def _print_query(url: str, max_file_size: int, pattern_type: str, pattern: str) -> None:
    """Print a formatted summary of the query details for debugging.

    Parameters
    ----------
    url : str
        The URL associated with the query.
    max_file_size : int
        The maximum file size allowed for the query, in bytes.
    pattern_type : str
        Specifies the type of pattern to use, either "include" or "exclude".
    pattern : str
        The actual pattern string to include or exclude in the query.

    """
    print(f"{Colors.WHITE}{url:<20}{Colors.END}", end="")
    if int(max_file_size / 1024) != DEFAULT_FILE_SIZE_KB:
        print(
            f" | {Colors.YELLOW}Size: {int(max_file_size / 1024)}kb{Colors.END}",
            end="",
        )
    if pattern_type == "include" and pattern != "":
        print(f" | {Colors.YELLOW}Include {pattern}{Colors.END}", end="")
    elif pattern_type == "exclude" and pattern != "":
        print(f" | {Colors.YELLOW}Exclude {pattern}{Colors.END}", end="")


def _print_error(url: str, exc: Exception, max_file_size: int, pattern_type: str, pattern: str) -> None:
    """Print a formatted error message for debugging.

    Parameters
    ----------
    url : str
        The URL associated with the query that caused the error.
    exc : Exception
        The exception raised during the query or process.
    max_file_size : int
        The maximum file size allowed for the query, in bytes.
    pattern_type : str
        Specifies the type of pattern to use, either "include" or "exclude".
    pattern : str
        The actual pattern string to include or exclude in the query.

    """
    print(f"{Colors.BROWN}WARN{Colors.END}: {Colors.RED}<-  {Colors.END}", end="")
    _print_query(url, max_file_size, pattern_type, pattern)
    print(f" | {Colors.RED}{exc}{Colors.END}")


def _print_success(url: str, max_file_size: int, pattern_type: str, pattern: str, summary: str) -> None:
    """Print a formatted success message for debugging.

    Parameters
    ----------
    url : str
        The URL associated with the successful query.
    max_file_size : int
        The maximum file size allowed for the query, in bytes.
    pattern_type : str
        Specifies the type of pattern to use, either "include" or "exclude".
    pattern : str
        The actual pattern string to include or exclude in the query.
    summary : str
        A summary of the query result, including details like estimated tokens.

    """
    estimated_tokens = summary[summary.index("Estimated tokens:") + len("Estimated ") :]
    print(f"{Colors.GREEN}INFO{Colors.END}: {Colors.GREEN}<-  {Colors.END}", end="")
    _print_query(url, max_file_size, pattern_type, pattern)
    print(f" | {Colors.PURPLE}{estimated_tokens}{Colors.END}")
