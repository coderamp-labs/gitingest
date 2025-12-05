"""Module for extracting files from a gitingest digest."""

from __future__ import annotations

import os
import re
from pathlib import Path

from gitingest.schemas.filesystem import SEPARATOR
from gitingest.utils.logging_config import get_logger

logger = get_logger(__name__)


def extract(digest_path: str | Path, output_dir: str | Path = ".") -> None:
    """Extract files from a gitingest digest file.

    Parameters
    ----------
    digest_path : str | Path
        Path to the digest file.
    output_dir : str | Path
        Directory where extracted files will be saved.

    """
    digest_path = Path(digest_path)
    output_dir = Path(output_dir)

    if not digest_path.exists():
        raise FileNotFoundError(f"Digest file not found: {digest_path}")

    logger.info("Reading digest file", extra={"digest_path": str(digest_path)})
    with digest_path.open("r", encoding="utf-8") as f:
        content = f.read()

    # Create the output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Regex to identify file blocks
    # Format:
    # ================================================
    # FILE: path/to/file
    # ================================================
    # content...
    separator_pattern = re.escape(SEPARATOR)
    pattern = re.compile(
        rf"^{separator_pattern}\n(FILE|SYMLINK): (.+)\n{separator_pattern}\n",
        re.MULTILINE,
    )

    matches = list(pattern.finditer(content))

    if not matches:
        logger.warning("No files found in the digest.")
        return

    logger.info(f"Found {len(matches)} files to extract.")

    for i, match in enumerate(matches):
        node_type = match.group(1)
        path_info = match.group(2).strip()

        # Calculate content range
        start_idx = match.end()
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(content)

        # Extract content and remove trailing newlines added during ingestion
        file_content = content[start_idx:end_idx]
        # The ingestion process adds "\n\n" to content_string and joins with "\n", so we expect 3 newlines.
        if file_content.endswith("\n\n\n"):
            file_content = file_content[:-3]

        if node_type == "SYMLINK":
            # SYMLINK: source -> target
            if " -> " in path_info:
                link_path_str, target_path_str = path_info.split(" -> ", 1)
                link_full_path = output_dir / link_path_str

                # Ensure parent dir exists
                link_full_path.parent.mkdir(parents=True, exist_ok=True)

                # Create symlink
                # We need to be careful with existing files
                if link_full_path.exists() or link_full_path.is_symlink():
                    link_full_path.unlink()

                try:
                    os.symlink(target_path_str, link_full_path)
                    logger.debug(
                        f"Created symlink: {link_full_path} -> {target_path_str}"
                    )
                except OSError as e:
                    logger.error(f"Failed to create symlink {link_full_path}: {e}")
            else:
                logger.warning(f"Invalid symlink format: {path_info}")

        else:
            # FILE: path
            # path_info is the file path
            target_file_path = output_dir / path_info

            # Ensure parent dir exists
            target_file_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                with target_file_path.open("w", encoding="utf-8") as f:
                    f.write(file_content)
                logger.debug(f"Extracted: {target_file_path}")
            except OSError as e:
                logger.error(f"Failed to write file {target_file_path}: {e}")

    logger.info("Extraction complete.")
