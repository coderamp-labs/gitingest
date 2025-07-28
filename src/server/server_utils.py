"""Utility functions for the server."""

import asyncio
import logging
import shutil
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from gitingest.config import TMP_BASE_PATH
from server.server_config import DELETE_REPO_AFTER

# Initialize a rate limiter
limiter = Limiter(key_func=get_remote_address)

logger = logging.getLogger(__name__)


async def rate_limit_exception_handler(request: Request, exc: Exception) -> Response:
    """Handle rate-limiting errors with a custom exception handler.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.
    exc : Exception
        The exception raised, expected to be RateLimitExceeded.

    Returns
    -------
    Response
        A response indicating that the rate limit has been exceeded.

    Raises
    ------
    exc
        If the exception is not a RateLimitExceeded error, it is re-raised.

    """
    if isinstance(exc, RateLimitExceeded):
        # Delegate to the default rate limit handler
        return _rate_limit_exceeded_handler(request, exc)
    # Re-raise other exceptions
    raise exc


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup & graceful-shutdown tasks for the FastAPI app.

    Returns
    -------
    AsyncGenerator[None, None]
        Yields control back to the FastAPI application while the background task runs.

    """
    task = asyncio.create_task(_remove_old_repositories())

    yield  # app runs while the background task is alive

    task.cancel()  # ask the worker to stop
    with suppress(asyncio.CancelledError):
        await task  # swallow the cancellation signal


async def _remove_old_repositories(
    base_path: Path = TMP_BASE_PATH,
    scan_interval: int = 60,
    delete_after: int = DELETE_REPO_AFTER,
) -> None:
    """Periodically delete old repositories/directories.

    Every ``scan_interval`` seconds the coroutine scans ``base_path`` and deletes directories older than
    ``delete_after`` seconds. The repository URL is extracted from the first ``.txt`` file in each directory
    and appended to ``history.txt``, assuming the filename format: "owner-repository.txt". Filesystem errors are
    logged and the loop continues.

    Parameters
    ----------
    base_path : Path
        The path to the base directory where repositories are stored (default: ``TMP_BASE_PATH``).
    scan_interval : int
        The number of seconds between scans (default: 60).
    delete_after : int
        The number of seconds after which a repository is considered old and will be deleted
        (default: ``DELETE_REPO_AFTER``).

    """
    while True:
        if not base_path.exists():
            await asyncio.sleep(scan_interval)
            continue

        now = time.time()
        try:
            for folder in base_path.iterdir():
                if now - folder.stat().st_ctime <= delete_after:  # Not old enough
                    continue

                await _process_folder(folder)

        except (OSError, PermissionError):
            logger.exception("Exception in _remove_old_repositories")

        await asyncio.sleep(scan_interval)


async def _process_folder(folder: Path) -> None:
    """Append the repo URL (if discoverable) to ``history.txt`` and delete ``folder``.

    Parameters
    ----------
    folder : Path
        The path to the folder to be processed.

    """
    history_file = Path("history.txt")
    loop = asyncio.get_running_loop()

    try:
        first_txt_file = next(folder.glob("*.txt"))
    except StopIteration:  # No .txt file found
        return

    # Append owner/repo to history.txt
    try:
        filename = first_txt_file.stem  # "owner-repo"
        if "-" in filename:
            owner, repo = filename.split("-", 1)
            repo_url = f"{owner}/{repo}"
            await loop.run_in_executor(None, _append_line, history_file, repo_url)
    except (OSError, PermissionError):
        logger.exception("Exception raised while processing folder %s", folder)

    # Delete the cloned repo
    try:
        await loop.run_in_executor(None, shutil.rmtree, folder)
    except PermissionError:
        logger.exception("No permission to delete %s", folder)
    except OSError:
        logger.exception("Could not delete %s", folder)


def _append_line(path: Path, line: str) -> None:
    """Append a line to a file.

    Parameters
    ----------
    path : Path
        The path to the file to append the line to.
    line : str
        The line to append to the file.

    """
    with path.open("a", encoding="utf-8") as fp:
        fp.write(f"{line}\n")


## Color printing utility
class Colors:
    """ANSI color codes."""

    BLACK = "\033[0;30m"
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    BROWN = "\033[0;33m"
    BLUE = "\033[0;34m"
    PURPLE = "\033[0;35m"
    CYAN = "\033[0;36m"
    LIGHT_GRAY = "\033[0;37m"
    DARK_GRAY = "\033[1;30m"
    LIGHT_RED = "\033[1;31m"
    LIGHT_GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    LIGHT_BLUE = "\033[1;34m"
    LIGHT_PURPLE = "\033[1;35m"
    LIGHT_CYAN = "\033[1;36m"
    WHITE = "\033[1;37m"
    BOLD = "\033[1m"
    FAINT = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    NEGATIVE = "\033[7m"
    CROSSED = "\033[9m"
    END = "\033[0m"
