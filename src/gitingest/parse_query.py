import os
import string
import uuid
from typing import Any, Dict, List, Optional, Union
from urllib.parse import unquote

from gitingest.ignore_patterns import DEFAULT_IGNORE_PATTERNS

TMP_BASE_PATH = "../tmp"
HEX_DIGITS = set(string.hexdigits)


def parse_url(url: str) -> Dict[str, Any]:
    parsed = {
        "user_name": None,
        "repo_name": None,
        "type": None,
        "branch": None,
        "commit": None,
        "subpath": "/",
        "local_path": None,
        "url": None,
        "slug": None,
        "id": None,
    }

    url = url.split(" ")[0]
    url = unquote(url)  # Decode URL-encoded characters

    if not url.startswith('https://'):
        url = 'https://' + url

    # Extract domain and path
    url_parts = url.split('/')
    domain = url_parts[2]
    path_parts = url_parts[3:]

    if len(path_parts) < 2:
        raise ValueError("Invalid repository URL. Please provide a valid Git repository URL.")

    parsed["user_name"] = path_parts[0]
    parsed["repo_name"] = path_parts[1]

    # Keep original URL format but with decoded components
    parsed["url"] = f"https://{domain}/{parsed['user_name']}/{parsed['repo_name']}"
    parsed['slug'] = f"{parsed['user_name']}-{parsed['repo_name']}"
    parsed["id"] = str(uuid.uuid4())
    parsed["local_path"] = f"{TMP_BASE_PATH}/{parsed['id']}/{parsed['slug']}"

    if len(path_parts) > 3:

        parsed["type"] = path_parts[2]  # Usually 'tree' or 'blob'

        # Find the commit hash or reconstruct the branch name
        remaining_parts = path_parts[3:]
        if remaining_parts[0] and len(remaining_parts[0]) == 40 and all(c in HEX_DIGITS for c in remaining_parts[0]):
            parsed["commit"] = remaining_parts[0]
            parsed["subpath"] = "/" + "/".join(remaining_parts[1:]) if len(remaining_parts) > 1 else "/"
        else:
            # Handle branch names with slashes and special characters
            for i, part in enumerate(remaining_parts):
                if part in ('tree', 'blob'):
                    # Found another type indicator, everything before this was the branch name
                    parsed["branch"] = "/".join(remaining_parts[:i])
                    parsed["subpath"] = (
                        "/" + "/".join(remaining_parts[i + 2 :]) if len(remaining_parts) > i + 2 else "/"
                    )
                    break
            else:
                # No additional type indicator found, assume everything is part of the branch name
                parsed["branch"] = "/".join(remaining_parts)
                parsed["subpath"] = "/"

    return parsed


def normalize_pattern(pattern: str) -> str:
    pattern = pattern.lstrip(os.sep)
    if pattern.endswith(os.sep):
        pattern += "*"
    return pattern


def parse_patterns(pattern: Union[List[str], str]) -> List[str]:
    patterns = pattern if isinstance(pattern, list) else [pattern]
    patterns = [p.strip() for p in patterns]

    for p in patterns:
        if not all(c.isalnum() or c in "-_./+*" for c in p):
            raise ValueError(
                f"Pattern '{p}' contains invalid characters. Only alphanumeric characters, dash (-), "
                "underscore (_), dot (.), forward slash (/), plus (+), and asterisk (*) are allowed."
            )

    return [normalize_pattern(p) for p in patterns]


def override_ignore_patterns(ignore_patterns: List[str], include_patterns: List[str]) -> List[str]:
    """
    Removes patterns from ignore_patterns that are present in include_patterns using set difference.

    Parameters
    ----------
    ignore_patterns : List[str]
        The list of patterns to potentially remove.
    include_patterns : List[str]
        The list of patterns to exclude from ignore_patterns.

    Returns
    -------
    List[str]
        A new list of ignore_patterns with specified patterns removed.
    """
    return list(set(ignore_patterns) - set(include_patterns))


def parse_path(path: str) -> Dict[str, Any]:
    query = {
        "url": None,
        "local_path": os.path.abspath(path),
        "slug": os.path.basename(os.path.dirname(path)) + "/" + os.path.basename(path),
        "subpath": "/",
        "id": str(uuid.uuid4()),
    }
    return query


def parse_query(
    source: str,
    max_file_size: int,
    from_web: bool,
    include_patterns: Optional[Union[List[str], str]] = None,
    ignore_patterns: Optional[Union[List[str], str]] = None,
) -> Dict[str, Any]:
    """
    Parses the input source to construct a query dictionary with specified parameters.

    Parameters
    ----------
    source : str
        The source URL or file path to parse.
    max_file_size : int
        The maximum file size in bytes to include.
    from_web : bool
        Flag indicating whether the source is a web URL.
    include_patterns : Optional[Union[List[str], str]], optional
        Patterns to include, by default None. Can be a list of strings or a single string.
    ignore_patterns : Optional[Union[List[str], str]], optional
        Patterns to ignore, by default None. Can be a list of strings or a single string.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the parsed query parameters, including 'max_file_size',
        'ignore_patterns', and 'include_patterns'.
    """
    # Determine the parsing method based on the source type
    if from_web or source.startswith("https://") or "github.com" in source:
        query = parse_url(source)
    else:
        query = parse_path(source)

    # Process ignore patterns
    ignore_patterns_list = DEFAULT_IGNORE_PATTERNS.copy()
    if ignore_patterns:
        ignore_patterns_list += parse_patterns(ignore_patterns)

    # Process include patterns and override ignore patterns accordingly
    if include_patterns:
        parsed_include = parse_patterns(include_patterns)
        ignore_patterns_list = override_ignore_patterns(ignore_patterns_list, include_patterns=parsed_include)
    else:
        parsed_include = None

    # Update the query dictionary with max_file_size and processed patterns
    query.update(
        {
            'max_file_size': max_file_size,
            'ignore_patterns': ignore_patterns_list,
            'include_patterns': parsed_include,
        }
    )
    return query
