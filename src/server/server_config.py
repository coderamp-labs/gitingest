"""Configuration for the server."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.templating import Jinja2Templates

MAX_DISPLAY_SIZE: int = 300_000

# Slider configuration (if updated, update the logSliderToSize function in src/static/js/utils.js)
DEFAULT_FILE_SIZE_KB: int = 5 * 1024  # 5 mb
MAX_FILE_SIZE_KB: int = 100 * 1024  # 100 mb

EXAMPLE_REPOS: list[dict[str, str]] = [
    {"name": "Gitingest", "url": "https://github.com/coderamp-labs/gitingest"},
    {"name": "FastAPI", "url": "https://github.com/fastapi/fastapi"},
    {"name": "Flask", "url": "https://github.com/pallets/flask"},
    {"name": "Excalidraw", "url": "https://github.com/excalidraw/excalidraw"},
    {"name": "ApiAnalytics", "url": "https://github.com/tom-draper/api-analytics"},
]


# Version and repository configuration
VERSION = os.getenv("VERSION", "unknown")
REPOSITORY_URL = os.getenv("REPOSITORY_URL", "https://github.com/coderamp-labs/gitingest")

# Minimum number of parts expected in branch-commit format (e.g., "main-abc1234")
MIN_BRANCH_COMMIT_PARTS = 2


def get_version_info() -> dict[str, str]:
    """Get version information including display version and link.

    Returns
    -------
    dict[str, str]
        Dictionary containing 'version' and 'version_link' keys.

    """
    version = VERSION
    repo_url = REPOSITORY_URL.rstrip("/")

    # Check if version looks like a tag (doesn't contain branch-commit pattern)
    if version != "unknown" and "-" in version and len(version.split("-")) >= MIN_BRANCH_COMMIT_PARTS:
        # This looks like branch-commit format (e.g., "main-abc1234")
        parts = version.split("-")
        if len(parts) >= MIN_BRANCH_COMMIT_PARTS:
            # Take the last part as commit hash
            commit_hash = parts[-1]
            version_link = f"{repo_url}/commit/{commit_hash}"
        else:
            # Fallback to main branch
            version_link = f"{repo_url}/tree/main"
    elif version != "unknown":
        # This looks like a tag version
        version_link = f"{repo_url}/releases/tag/{version}"
    else:
        # Unknown version, link to main branch
        version_link = f"{repo_url}/tree/main"

    return {
        "version": version,
        "version_link": version_link,
    }


# Use absolute path to templates directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)
