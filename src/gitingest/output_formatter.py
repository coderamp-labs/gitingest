"""Functions to ingest and analyze a codebase directory or single file."""

from __future__ import annotations

import ssl
from functools import singledispatchmethod
from pathlib import Path
from typing import TYPE_CHECKING

import requests.exceptions
import tiktoken
from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound

from gitingest.schemas import ContextV1, FileSystemNode, Source
from gitingest.schemas.filesystem import SEPARATOR, FileSystemNodeType
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


def generate_digest(context: ContextV1) -> str:
    """Generate a digest string from a ContextV1 object.

    This is a convenience function that uses the DefaultFormatter to format a ContextV1.

    Parameters
    ----------
    context : ContextV1
        The ContextV1 object containing sources and query information.

    Returns
    -------
    str
        The formatted digest string.

    """
    formatter = DefaultFormatter()
    return formatter.format(context, context.query)


class DefaultFormatter:
    """Default formatter for rendering filesystem nodes using Jinja2 templates."""

    def __init__(self) -> None:
        self.separator = SEPARATOR
        template_dir = Path(__file__).parent / "format" / "DefaultFormatter"
        self.env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)

    def _get_template_for_node(self, node: Source) -> Template:
        """Get template based on node class name."""
        template_name = f"{node.__class__.__name__}.j2"
        return self.env.get_template(template_name)

    @singledispatchmethod
    def format(self, node: Source, query: IngestionQuery) -> str:
        """Dynamically format any node type based on available templates."""
        try:
            template = self._get_template_for_node(node)
            # Provide common template variables
            context_vars = {
                "node": node,
                "query": query,
                "formatter": self,
                "SEPARATOR": SEPARATOR,
            }
            # Special handling for ContextV1 objects
            if isinstance(node, ContextV1):
                context_vars["context"] = node
                # Use ContextV1 for backward compatibility
                template = self.env.get_template("ContextV1.j2")

            return template.render(**context_vars)
        except TemplateNotFound:
            # Fallback: return content if available, otherwise empty string
            return f"{getattr(node, 'content', '')}"


class DebugFormatter:
    """Debug formatter that shows detailed information about filesystem nodes."""

    def __init__(self) -> None:
        self.separator = SEPARATOR
        template_dir = Path(__file__).parent / "format" / "DebugFormatter"
        self.env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)

    def _get_template_for_node(self, node: Source) -> Template:
        """Get template based on node class name."""
        template_name = f"{node.__class__.__name__}.j2"
        return self.env.get_template(template_name)

    @singledispatchmethod
    def format(self, node: Source, query: IngestionQuery) -> str:
        """Dynamically format any node type with debug information."""
        try:
            # Get the actual class name
            class_name = node.__class__.__name__

            # Get all field names (both from dataclass fields and regular attributes)
            field_names = []

            # Try to get dataclass fields first
            def _raise_no_dataclass_fields() -> None:
                msg = "No dataclass fields found"
                raise AttributeError(msg)

            try:
                if hasattr(node, "__dataclass_fields__") and hasattr(node.__dataclass_fields__, "keys"):
                    field_names.extend(node.__dataclass_fields__.keys())
                else:
                    _raise_no_dataclass_fields()  # Fall through to backup method
            except (AttributeError, TypeError):
                # Fall back to getting all non-private attributes
                field_names = [
                    attr for attr in dir(node) if not attr.startswith("_") and not callable(getattr(node, attr, None))
                ]

            # Format the debug output
            fields_str = ", ".join(field_names)

            # Try to get specific template, fallback to Source.j2
            try:
                template = self._get_template_for_node(node)
            except TemplateNotFound:
                template = self.env.get_template("Source.j2")

            return template.render(
                SEPARATOR=SEPARATOR,
                class_name=class_name,
                fields_str=fields_str,
                node=node,
                query=query,
                formatter=self,
            )
        except TemplateNotFound:
            # Ultimate fallback
            return f"DEBUG: {node.__class__.__name__}"


class SummaryFormatter:
    """Dedicated formatter for generating summaries of filesystem nodes."""

    def __init__(self) -> None:
        template_dir = Path(__file__).parent / "format" / "SummaryFormatter"
        self.env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)

    def _get_template_for_node(self, node: Source) -> Template:
        """Get template based on node class name."""
        template_name = f"{node.__class__.__name__}.j2"
        return self.env.get_template(template_name)

    @singledispatchmethod
    def summary(self, node: Source, query: IngestionQuery) -> str:
        """Dynamically generate summary for any node type based on available templates."""
        try:
            # Provide common template variables
            context_vars = {
                "node": node,
                "query": query,
                "formatter": self,
            }

            # Special handling for ContextV1 objects
            if isinstance(node, ContextV1):
                context_vars["context"] = node
                # Use ContextV1 for backward compatibility
                template = self.env.get_template("ContextV1.j2")
            else:
                template = self._get_template_for_node(node)

            return template.render(**context_vars)
        except TemplateNotFound:
            # Fallback: return name if available
            return f"{getattr(node, 'name', '')}"
