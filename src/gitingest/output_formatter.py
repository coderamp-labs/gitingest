"""Functions to ingest and analyze a codebase directory or single file."""

from __future__ import annotations

import ssl
from functools import singledispatchmethod
from typing import TYPE_CHECKING

import requests.exceptions
import tiktoken
from jinja2 import BaseLoader, Environment

from gitingest.schemas import FileSystemDirectory, FileSystemFile, FileSystemNode, FileSystemSymlink, Source
from gitingest.schemas.filesystem import SEPARATOR, Context, FileSystemNodeType, GitRepository
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


# Backward compatibility


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

    tree_str += f"{prefix}{current_prefix}{display_name}\n"

    if node.type == FileSystemNodeType.DIRECTORY and node.children:
        prefix += "    " if is_last else "│   "
        for i, child in enumerate(node.children):
            tree_str += _create_tree_structure(query, node=child, prefix=prefix, is_last=i == len(node.children) - 1)
    return tree_str


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
        encoding = tiktoken.get_encoding("o200k_base")  # gpt-4o, gpt-4o-mini
        total_tokens = len(encoding.encode(text, disallowed_special=()))
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


def generate_digest(context: Context) -> str:
    """Generate a digest string from a Context object.
    
    This is a convenience function that uses the DefaultFormatter to format a Context.
    
    Parameters
    ----------
    context : Context
        The Context object containing sources and query information.
    
    Returns
    -------
    str
        The formatted digest string.
    """
    formatter = DefaultFormatter()
    return formatter.format(context, context.query)


class DefaultFormatter:
    def __init__(self):
        self.separator = SEPARATOR
        self.env = Environment(loader=BaseLoader())

    @singledispatchmethod
    def format(self, node: Source, query):
        return f"{getattr(node, 'content', '')}"

    @format.register
    def _(self, node: FileSystemFile, query):
        template = """
{{ SEPARATOR }}
{{ node.name }}
{{ SEPARATOR }}
{{ node.content }}
"""
        file_template = self.env.from_string(template)
        return file_template.render(SEPARATOR=SEPARATOR, node=node, query=query, formatter=self)

    @format.register
    def _(self, node: FileSystemDirectory, query):
        template = """{%- if node.depth == 0 %}{{ node.name }}:
{{ node.tree }}

{% endif -%}
{%- for child in node.children -%}
{{ formatter.format(child, query) }}
{%- endfor -%}"""
        dir_template = self.env.from_string(template)
        return dir_template.render(node=node, query=query, formatter=self)

    @format.register
    def _(self, node: GitRepository, query):
        template = """{%- if node.depth == 0 %}🔗 Git Repository: {{ node.name }}
{{ node.tree }}

{% endif -%}
{%- for child in node.children -%}
{{ formatter.format(child, query) }}
{%- endfor -%}"""
        git_template = self.env.from_string(template)
        return git_template.render(node=node, query=query, formatter=self)

    @format.register
    def _(self, node: FileSystemSymlink, query):
        template = """
{{ SEPARATOR }}
{{ node.name }}{% if node.target %} -> {{ node.target }}{% endif %}
{{ SEPARATOR }}
"""
        symlink_template = self.env.from_string(template)
        return symlink_template.render(SEPARATOR=SEPARATOR, node=node, query=query, formatter=self)

    @format.register
    def _(self, context: Context, query):
        """Format a Context by formatting all its sources."""
        template = \
"""# Generated using https://gitingest.com/{{ context.query.user_name }}/{{ context.query.repo_name }}

Sources used:
{%- for source in context.sources %}
- {{ source.name }}: {{ source.__class__.__name__ }}
{% endfor %}

{%- for source in context.sources %}
{{ formatter.format(source, context.query) }}
{%- endfor %}
# End of generated content"""
        context_template = self.env.from_string(template)
        return context_template.render(context=context, formatter=self)


class DebugFormatter:
    def __init__(self):
        self.separator = SEPARATOR
        self.env = Environment(loader=BaseLoader())

    @singledispatchmethod
    def format(self, node: Source, query):
        """Format any Source type with debug information."""
        # Get the actual class name
        class_name = node.__class__.__name__

        # Get all field names (both from dataclass fields and regular attributes)
        field_names = []

        # Try to get dataclass fields first
        try:
            if hasattr(node, "__dataclass_fields__") and hasattr(node.__dataclass_fields__, "keys"):
                field_names.extend(node.__dataclass_fields__.keys())
            else:
                raise AttributeError  # Fall through to backup method
        except (AttributeError, TypeError):
            # Fall back to getting all non-private attributes
            field_names = [
                attr for attr in dir(node) if not attr.startswith("_") and not callable(getattr(node, attr, None))
            ]

        # Format the debug output
        fields_str = ", ".join(field_names)
        template = """
{{ SEPARATOR }}
DEBUG: {{ class_name }}
Fields: {{ fields_str }}
{{ SEPARATOR }}
"""
        debug_template = self.env.from_string(template)
        return debug_template.render(
            SEPARATOR=SEPARATOR,
            class_name=class_name,
            fields_str=fields_str,
        )


class SummaryFormatter:
    """Dedicated formatter for generating summaries of filesystem nodes."""

    def __init__(self):
        self.env = Environment(loader=BaseLoader())

    @singledispatchmethod
    def summary(self, node: Source, query):
        return f"{getattr(node, 'name', '')}"

    @summary.register
    def _(self, node: FileSystemDirectory, query):
        template = """ \
Directory structure:
{{ node.tree }}
"""
        summary_template = self.env.from_string(template)
        return summary_template.render(node=node, query=query)

    @summary.register
    def _(self, context: Context, query):
        template = """
Repository: {{ context.query.user_name }}/{{ context.query.repo_name }}
Commit: {{ context.query.commit }}
Files analyzed: {{ context.sources[0].file_count }}
"""
        summary_template = self.env.from_string(template)
        return summary_template.render(context=context, query=query)
