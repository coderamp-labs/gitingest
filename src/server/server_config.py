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

# Minimum length for a git commit hash
MIN_COMMIT_HASH_LENGTH = 6

# Minimum number of parts in PR format to include commit hash (pr-number-commit)
MIN_PR_PARTS_WITH_COMMIT = 2


def get_version_info() -> dict[str, str]:
    """Get version information including display version and link.

    Returns
    -------
    dict[str, str]
        Dictionary containing 'version' and 'version_link' keys.

    """
    version = VERSION
    repo_url = REPOSITORY_URL.rstrip("/")
    display_version = version
    version_link = f"{repo_url}/tree/main"  # Default fallback

    def _looks_like_commit_hash(text: str) -> bool:
        """Check if text looks like a git commit hash (alphanumeric, 6+ chars)."""
        return len(text) >= MIN_COMMIT_HASH_LENGTH and text.isalnum() and any(c.isalpha() for c in text)

    # Check if version contains dashes
    if version != "unknown" and ("-" in version):
        parts = version.split("-")
        if len(parts) >= MIN_BRANCH_COMMIT_PARTS:
            # Check if first part indicates a PR
            if parts[0].lower() in ("pr", "pull"):
                # Extract PR number and commit hash from the parts
                try:
                    pr_number = int(parts[1])
                    display_version = f"pr-{pr_number}"
                    # If there's a commit hash after the PR number, link to the commit in the PR
                    if len(parts) > MIN_PR_PARTS_WITH_COMMIT:
                        commit_hash = parts[-1]
                        version_link = f"{repo_url}/pull/{pr_number}/commits/{commit_hash}"
                    else:
                        # No commit hash, link to the PR page
                        version_link = f"{repo_url}/pull/{pr_number}"
                except (ValueError, IndexError):
                    # If PR number is invalid, fallback to main branch
                    display_version = version
                    version_link = f"{repo_url}/tree/main"
            elif _looks_like_commit_hash(parts[-1]):
                # This looks like branch-commit format (e.g., "main-abc1234")
                # Display only the branch name, link to the commit
                branch_name = parts[0]
                commit_hash = parts[-1]
                display_version = branch_name
                version_link = f"{repo_url}/commit/{commit_hash}"
            else:
                # This looks like a tag version with dashes (e.g., "release-2.1.0")
                display_version = version
                version_link = f"{repo_url}/releases/tag/{version}"
        else:
            # Fallback to main branch
            display_version = version
            version_link = f"{repo_url}/tree/main"
    elif version != "unknown":
        # This looks like a tag version
        display_version = version
        version_link = f"{repo_url}/releases/tag/{version}"
    else:
        # Unknown version, link to main branch
        display_version = "unknown"
        version_link = f"{repo_url}/tree/main"

    return {
        "version": display_version,
        "version_link": version_link,
    }


# Use absolute path to templates directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)
