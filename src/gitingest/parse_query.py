import os
import string
import uuid
from typing import Any
from urllib.parse import unquote

from gitingest.ignore_patterns import DEFAULT_IGNORE_PATTERNS

TMP_BASE_PATH = "../tmp"
HEX_DIGITS = set(string.hexdigits)


def parse_url(url: str) -> dict[str, Any]:
    url = url.split(" ")[0]
    url = unquote(url)  # Decode URL-encoded characters

    if not url.startswith("https://"):
        url = "https://" + url

    # Extract domain and path
    url_parts = url.split("/")
    domain = url_parts[2]
    path_parts = url_parts[3:]

    if len(path_parts) < 2:
        raise ValueError("Invalid repository URL. Please provide a valid Git repository URL.")

    user_name = path_parts[0]
    repo_name = path_parts[1]
    _id = str(uuid.uuid4())
    slug = f"{user_name}-{repo_name}"

    parsed = {
        "user_name": user_name,
        "repo_name": repo_name,
        "type": None,
        "branch": None,
        "commit": None,
        "subpath": "/",
        "local_path": f"{TMP_BASE_PATH}/{_id}/{slug}",
        "url": f"https://{domain}/{user_name}/{repo_name}",
        "slug": slug,
        "id": _id,
    }

    # If this is an issues page, return early without processing subpath
    if len(path_parts) > 2 and (path_parts[2] == "issues" or path_parts[2] == "pull"):
        return parsed

    if len(path_parts) < 4:
        return parsed

    parsed["type"] = path_parts[2]  # Usually 'tree' or 'blob'
    commit = path_parts[3]

    if _is_valid_git_commit_hash(commit):
        parsed["commit"] = commit
        if len(path_parts) > 4:
            parsed["subpath"] += "/".join(path_parts[4:])
    else:
        parsed["branch"] = commit
        if len(path_parts) > 4:
            parsed["subpath"] += "/".join(path_parts[4:])

    return parsed


def _is_valid_git_commit_hash(commit: str) -> bool:
    return len(commit) == 40 and all(c in HEX_DIGITS for c in commit)


def normalize_pattern(pattern: str) -> str:
    """
    Normalize a pattern by stripping and formatting.

    Args:
        pattern (str): The ignore pattern.

    Returns:
        str: Normalized pattern.
    """
    pattern = pattern.strip()
    pattern = pattern.lstrip(os.sep)
    if pattern.endswith(os.sep):
        pattern += "*"
    return pattern


def parse_patterns(pattern: list[str] | str) -> list[str]:
    patterns = pattern if isinstance(pattern, list) else [pattern]
    patterns = [p.strip() for p in patterns]

    for p in patterns:
        if not all(c.isalnum() or c in "-_./+*" for c in p):
            raise ValueError(
                f"Pattern '{p}' contains invalid characters. Only alphanumeric characters, dash (-), "
                "underscore (_), dot (.), forward slash (/), plus (+), and asterisk (*) are allowed."
            )

    return [normalize_pattern(p) for p in patterns]


def override_ignore_patterns(ignore_patterns: list[str], include_patterns: list[str]) -> list[str]:
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


def parse_path(path: str) -> dict[str, Any]:
    query = {
        "url": None,
### 📝 **Parse Path**
def parse_path(path: str) -> dict:
    """
    Parse a local file path.

    Args:
        path (str): File path.

    Returns:
        dict: Parsed path details.
    """
    return {
        "local_path": os.path.abspath(path),
        "slug": os.path.basename(os.path.dirname(path)) + "/" + os.path.basename(path),
        "subpath": "/",
        "id": str(uuid.uuid4()),
        "url": None,
    }



def parse_query(
    source: str,
    max_file_size: int,
    from_web: bool,
    include_patterns: list[str] | str | None = None,
    ignore_patterns: list[str] | str | None = None,
) -> dict[str, Any]:
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
            "max_file_size": max_file_size,
            "ignore_patterns": ignore_patterns_list,
            "include_patterns": parsed_include,
        }
    )
    return query

### 📝 **Parse .gitignore**
def parse_gitignore(gitignore_path: str) -> List[str]:
    """
    Parse .gitignore and return ignore patterns.

    Args:
        gitignore_path (str): Path to the .gitignore file.

    Returns:
        List[str]: List of ignore patterns.
    """
    ignore_patterns = []
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Ensure directory patterns end with '/'
                    if os.path.isdir(os.path.join(os.path.dirname(gitignore_path), line)):
                        line = line.rstrip('/') + '/'
                    ignore_patterns.append(line)
    return ignore_patterns


### 📝 **Parse Query**
def parse_query(source: str, max_file_size: int, from_web: bool,
                include_patterns: Union[List[str], str] = None,
                ignore_patterns: Union[List[str], str] = None) -> dict:
    """
    Parse the query and apply ignore patterns.

    Args:
        source (str): Source path or URL.
        max_file_size (int): Maximum file size.
        from_web (bool): Web source or local.
        include_patterns (Union[List[str], str]): Include patterns.
        ignore_patterns (Union[List[str], str]): Ignore patterns.

    Returns:
        dict: Query object with patterns.
    """
    if from_web:
        query = parse_url(source)
    else:
        query = parse_path(source)
    
    query['max_file_size'] = max_file_size

    # Start with default ignore patterns
    final_ignore_patterns = DEFAULT_IGNORE_PATTERNS.copy()

    # Load from .gitignore
    gitignore_path = os.path.join(query['local_path'], '.gitignore')
    print(f"find .gitignore on project --> {gitignore_path}")

    if os.path.exists(gitignore_path):
        gitignore_patterns = parse_gitignore(gitignore_path)
        final_ignore_patterns.extend(gitignore_patterns)
        print(f"\n🛡️  Patterns from: {gitignore_path}")
        for pattern in gitignore_patterns:
            print(f"  - {pattern}")
    # Add user-defined ignore patterns
    if ignore_patterns:
        final_ignore_patterns.extend(parse_patterns(ignore_patterns))
    
    # Handle include patterns
    if include_patterns:
        include_patterns = parse_patterns(include_patterns)
        final_ignore_patterns = override_ignore_patterns(final_ignore_patterns, include_patterns)
    
    query['ignore_patterns'] = final_ignore_patterns
    query['include_patterns'] = include_patterns
    # 🖨️ Print patterns to the console
    print("\n🛡️  Applied Ignore Patterns:")
    for pattern in final_ignore_patterns:
        print(f"  - {pattern}")
    
    if include_patterns:
        print("\n✅ Included Patterns:")
        for pattern in include_patterns:
            print(f"  - {pattern}")
    else:
        print("\n✅ Included Patterns: None")

    return query
    return query