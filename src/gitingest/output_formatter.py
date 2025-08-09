"""Functions to ingest and analyze a codebase directory or single file."""

from __future__ import annotations

import ssl
from typing import TYPE_CHECKING

import requests.exceptions
import tiktoken

from gitingest.schemas import FileSystemNode, FileSystemNodeType
from gitingest.utils.compat_func import readlink
from gitingest.utils.logging_config import get_logger

if TYPE_CHECKING:
    from gitingest.schemas import IngestionQuery

# Initialize logger for this module
logger = get_logger(__name__)

_TOKEN_THRESHOLDS: list[tuple[int, str]] = [
    (1_000_000, "M"),
    (1_000, "k"),
]


def format_node(node: FileSystemNode, query: IngestionQuery) -> tuple[str, str, str]:
    """Generate a summary, directory structure, and file contents for a given file system node.

    If the node represents a directory, the function will recursively process its contents.

    Parameters
    ----------
    node : FileSystemNode
        The file system node to be summarized.
    query : IngestionQuery
        The parsed query object containing information about the repository and query parameters.

    Returns
    -------
    tuple[str, str, str]
        A tuple containing the summary, directory structure, and file contents.

    """
    is_single_file = node.type == FileSystemNodeType.FILE
    summary = _create_summary_prefix(query, single_file=is_single_file)

    if node.type == FileSystemNodeType.DIRECTORY:
        summary += f"Files analyzed: {node.file_count}\n"
    elif node.type == FileSystemNodeType.FILE:
        summary += f"File: {node.name}\n"
        summary += f"Lines: {len(node.content.splitlines()):,}\n"

    tree = "Directory structure:\n" + _create_tree_structure(query, node=node)

    content = _gather_file_contents(node)

    token_estimate = _format_token_count(tree + content)
    if token_estimate:
        summary += f"\nEstimated tokens: {token_estimate}"

    return summary, tree, content


def format_node_with_context_limit(
    node: FileSystemNode, 
    query: IngestionQuery, 
    max_tokens: int
) -> tuple[str, str, str]:
    """Generate optimized content that fits within token limit using greedy knapsack algorithm.
    
    Uses relevance scores to prioritize files and maximize value within token constraints.
    
    Parameters
    ----------
    node : FileSystemNode
        The file system node to be summarized.
    query : IngestionQuery
        The parsed query object containing information about the repository and query parameters.
    max_tokens : int
        Maximum tokens allowed for the output.
        
    Returns
    -------
    tuple[str, str, str]
        A tuple containing the summary, directory structure, and optimized file contents.
    """
    is_single_file = node.type == FileSystemNodeType.FILE
    summary = _create_summary_prefix(query, single_file=is_single_file)
    
    # Generate tree structure (always include this)
    tree = "Directory structure:\n" + _create_tree_structure(query, node=node)
    tree_tokens = _count_tokens(tree)
    
    # Reserve tokens for summary and tree
    summary_base_tokens = _count_tokens(summary) + 100  # 100 buffer for final summary additions
    available_tokens = max_tokens - tree_tokens - summary_base_tokens
    
    if available_tokens <= 0:
        # Not enough space even for tree, just return minimal content
        content = "[Content omitted - insufficient token space]"
        summary += f"\nEstimated tokens: {_format_token_count(summary + tree + content)}"
        return summary, tree, content
    
    # Apply greedy knapsack algorithm to select optimal file contents
    optimized_content = _optimize_content_with_knapsack(node, available_tokens)
    
    # Update summary with final info
    if node.type == FileSystemNodeType.DIRECTORY:
        # Count how many files were actually included
        included_files = int(len([line for line in optimized_content.split('\n') if line.startswith('=' * 48)]) / 2)
        summary += f"Files included: {included_files} (optimized for {max_tokens:,} tokens)\n"
    elif node.type == FileSystemNodeType.FILE:
        summary += f"File: {node.name}\n"
        summary += f"Lines: {len(node.content.splitlines()):,}\n"
    
    final_content = summary + "\n" + tree + "\n" + optimized_content
    token_estimate = _format_token_count(final_content)
    if token_estimate:
        summary += f"\nEstimated tokens: {token_estimate}"
    
    return summary, tree, optimized_content


def _create_summary_prefix(query: IngestionQuery, *, single_file: bool = False) -> str:
    """Create a prefix string for summarizing a repository or local directory.

    Includes repository name (if provided), commit/branch details, and subpath if relevant.

    Parameters
    ----------
    query : IngestionQuery
        The parsed query object containing information about the repository and query parameters.
    single_file : bool
        A flag indicating whether the summary is for a single file (default: ``False``).

    Returns
    -------
    str
        A summary prefix string containing repository, commit, branch, and subpath details.

    """
    parts = []

    if query.user_name:
        parts.append(f"Repository: {query.user_name}/{query.repo_name}")
    else:
        # Local scenario
        parts.append(f"Directory: {query.slug}")

    if query.tag:
        parts.append(f"Tag: {query.tag}")
    elif query.branch and query.branch not in ("main", "master"):
        parts.append(f"Branch: {query.branch}")

    if query.commit:
        parts.append(f"Commit: {query.commit}")

    if query.subpath != "/" and not single_file:
        parts.append(f"Subpath: {query.subpath}")

    return "\n".join(parts) + "\n"


def _gather_file_contents(node: FileSystemNode) -> str:
    """Recursively gather contents of all files under the given node.

    This function recursively processes a directory node and gathers the contents of all files
    under that node. It returns the concatenated content of all files as a single string.

    Parameters
    ----------
    node : FileSystemNode
        The current directory or file node being processed.

    Returns
    -------
    str
        The concatenated content of all files under the given node.

    """
    if node.type != FileSystemNodeType.DIRECTORY:
        return node.content_string

    # Recursively gather contents of all files under the current directory
    return "\n".join(_gather_file_contents(child) for child in node.children)


def _create_tree_structure(
    query: IngestionQuery,
    *,
    node: FileSystemNode,
    prefix: str = "",
    is_last: bool = True,
) -> str:
    """Generate a tree-like string representation of the file structure.

    This function generates a string representation of the directory structure, formatted
    as a tree with appropriate indentation for nested directories and files.

    Parameters
    ----------
    query : IngestionQuery
        The parsed query object containing information about the repository and query parameters.
    node : FileSystemNode
        The current directory or file node being processed.
    prefix : str
        A string used for indentation and formatting of the tree structure (default: ``""``).
    is_last : bool
        A flag indicating whether the current node is the last in its directory (default: ``True``).

    Returns
    -------
    str
        A string representing the directory structure formatted as a tree.

    """
    if not node.name:
        # If no name is present, use the slug as the top-level directory name
        node.name = query.slug

    tree_str = ""
    current_prefix = "└── " if is_last else "├── "

    # Indicate directories with a trailing slash
    display_name = node.name
    if node.type == FileSystemNodeType.DIRECTORY:
        display_name += "/"
    elif node.type == FileSystemNodeType.SYMLINK:
        display_name += " -> " + readlink(node.path).name
    
    # Add likelihood score if this file was selected by AI (score > 0)
    if node.likelihood_score > 0:
        # Color code based on score
        if node.likelihood_score >= 80:
            score_indicator = f" [🟢 {node.likelihood_score}%]"
        elif node.likelihood_score >= 60:
            score_indicator = f" [🟡 {node.likelihood_score}%]"
        elif node.likelihood_score >= 40:
            score_indicator = f" [🟠 {node.likelihood_score}%]"
        else:
            score_indicator = f" [🔴 {node.likelihood_score}%]"
        display_name += score_indicator

    tree_str += f"{prefix}{current_prefix}{display_name}\n"

    if node.type == FileSystemNodeType.DIRECTORY and node.children:
        prefix += "    " if is_last else "│   "
        for i, child in enumerate(node.children):
            tree_str += _create_tree_structure(query, node=child, prefix=prefix, is_last=i == len(node.children) - 1)
    return tree_str


def _count_tokens(text: str) -> int:
    """Count actual tokens in text using tiktoken.
    
    Parameters
    ----------
    text : str
        The text to count tokens for.
        
    Returns
    -------
    int
        Number of tokens, or character/4 estimate if tiktoken fails.
    """
    try:
        encoding = tiktoken.get_encoding("o200k_base")
        return len(encoding.encode(text, disallowed_special=()))
    except Exception:
        # Fallback to character-based estimation
        return len(text) // 4


def _format_token_count(text: str) -> str | None:
    """Return a human-readable token-count string (e.g. 1.2k, 1.2 M).

    Parameters
    ----------
    text : str
        The text string for which the token count is to be estimated.

    Returns
    -------
    str | None
        The formatted number of tokens as a string (e.g., ``"1.2k"``, ``"1.2M"``), or ``None`` if an error occurs.

    """
    try:
        total_tokens = _count_tokens(text)
    except (ValueError, UnicodeEncodeError) as exc:
        logger.warning("Failed to estimate token size", extra={"error": str(exc)})
        return None
    except (requests.exceptions.RequestException, ssl.SSLError) as exc:
        # If network errors, skip token count estimation instead of erroring out
        logger.warning("Failed to download tiktoken model", extra={"error": str(exc)})
        return None

    for threshold, suffix in _TOKEN_THRESHOLDS:
        if total_tokens >= threshold:
            return f"{total_tokens / threshold:.1f}{suffix}"

    return str(total_tokens)


def _optimize_content_with_knapsack(node: FileSystemNode, max_tokens: int) -> str:
    """Apply greedy knapsack algorithm to select optimal file contents within token limit.
    
    Parameters
    ----------
    node : FileSystemNode
        Root node to extract files from.
    max_tokens : int  
        Maximum tokens available for content.
        
    Returns
    -------
    str
        Optimized content string with selected files.
    """
    # Collect all files with their metadata
    file_items = []
    _collect_file_items(node, file_items)
    
    if not file_items:
        return "[No files found]"
    
    # Filter out files with 0 relevance (not AI-selected)
    relevant_items = [item for item in file_items if item['relevance'] > 0]
    
    if not relevant_items:
        return "[No relevant files found - all files have 0 AI relevance score]"
    
    # Calculate value/cost ratio for each relevant file
    for item in relevant_items:
        relevance_score = item['relevance']  # Already > 0, no need for max()
        
        file_type_multiplier = _get_file_type_multiplier(item['path'])
        # Value = relevance * type_multiplier * content_quality
        content_quality = _estimate_content_quality(item['content'])
        value = relevance_score * file_type_multiplier * content_quality
        
        # Cost = token count
        cost = item['tokens']
        
        # Ratio = value per token (higher is better)
        item['ratio'] = value / max(cost, 1)
    
    # Sort by ratio (descending - best value first)
    sorted_items = sorted(relevant_items, key=lambda x: x['ratio'], reverse=True)
    
    # Greedy selection: pick highest ratio items that fit
    selected_items = []
    total_tokens = 0
    
    for item in sorted_items:
        if total_tokens + item['tokens'] <= max_tokens:
            selected_items.append(item)
            total_tokens += item['tokens']
    
    # Build final content string
    if not selected_items:
        return "[No files fit within token limit]"
    
    content_parts = []
    for item in selected_items:
        content_parts.append(item['content_string'])
    
    result = "\n".join(content_parts)
    
    logger.info(
        f"Knapsack optimization: selected {len(selected_items)}/{len(relevant_items)} files, "
        f"using {total_tokens}/{max_tokens} tokens"
    )
    
    return result


def _collect_file_items(node: FileSystemNode, items: list) -> None:
    """Recursively collect file metadata for knapsack optimization.
    
    Parameters
    ----------
    node : FileSystemNode
        Current node to process.
    items : list
        List to append file items to.
    """
    if node.type == FileSystemNodeType.FILE:
        content_string = node.content_string
        tokens = _count_tokens(content_string)
        
        items.append({
            'path': node.path_str or node.name,
            'content': node.content,
            'content_string': content_string,
            'tokens': tokens,
            'relevance': node.likelihood_score,
            'size': node.size,
            'node': node
        })
    
    elif node.type == FileSystemNodeType.DIRECTORY and node.children:
        for child in node.children:
            _collect_file_items(child, items)


def _get_file_type_multiplier(file_path: str) -> float:
    """Get relevance multiplier based on file type/name.
    
    Parameters
    ---------- 
    file_path : str
        Path to the file.
        
    Returns
    -------
    float
        Multiplier for this file type (higher = more important).
    """
    from pathlib import Path
    
    path = Path(file_path)
    name_lower = path.name.lower()
    ext_lower = path.suffix.lower()
    
    # High priority files
    if any(pattern in name_lower for pattern in ['readme', 'main', 'index', 'app', 'server', '__init__']):
        return 2.0
    
    # Important code files
    if ext_lower in {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb'}:
        return 1.5
    
    # Config and setup files
    if ext_lower in {'.json', '.yaml', '.yml', '.toml', '.ini', '.env'} or name_lower in {'dockerfile', 'makefile'}:
        return 1.3
    
    # Documentation
    if ext_lower in {'.md', '.txt', '.rst'}:
        return 1.1
    
    # Default
    return 1.0


def _estimate_content_quality(content: str) -> float:
    """Estimate content quality/informativeness.
    
    Parameters
    ----------
    content : str
        File content to analyze.
        
    Returns
    -------
    float
        Quality score (higher = more informative).
    """
    if not content or content.strip() in ['[Binary file]', '[Empty file]', 'Error reading file']:
        return 0.1
    
    lines = content.splitlines()
    non_empty_lines = [line for line in lines if line.strip()]
    
    if not non_empty_lines:
        return 0.2
    
    # Base score from content density
    density = len(non_empty_lines) / max(len(lines), 1)
    
    # Bonus for code-like content
    code_indicators = 0
    for line in non_empty_lines[:50]:  # Check first 50 lines
        line_stripped = line.strip()
        if any(indicator in line_stripped for indicator in ['def ', 'class ', 'function ', 'import ', 'from ', 'const ', 'let ', 'var ']):
            code_indicators += 1
        if any(char in line_stripped for char in ['{', '}', '(', ')', ';', ':']):
            code_indicators += 0.5
    
    code_bonus = min(code_indicators / 10, 1.0)
    
    # Penalty for very long files (diminishing returns)
    length_penalty = 1.0
    if len(lines) > 1000:
        length_penalty = 0.8
    elif len(lines) > 2000:
        length_penalty = 0.6
    
    return (density + code_bonus) * length_penalty
