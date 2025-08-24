"""Model Context Protocol (MCP) server for Gitingest."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp.server import Server  # pylint: disable=import-error
from mcp.server.stdio import stdio_server  # pylint: disable=import-error
from mcp.types import TextContent, Tool  # pylint: disable=import-error
from prometheus_client import Counter

from gitingest.entrypoint import ingest_async
from gitingest.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

# Initialize logger for this module
logger = get_logger(__name__)

# Create Prometheus metrics
mcp_ingest_counter = Counter("gitingest_mcp_ingest_total", "Number of MCP ingests", ["status"])
mcp_tool_calls_counter = Counter("gitingest_mcp_tool_calls_total", "Number of MCP tool calls", ["tool_name", "status"])

# Create the MCP server instance
app = Server("gitingest")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="ingest_repository",
            description="Ingest a Git repository or local directory and return a structured digest for LLMs",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Git repository URL or local directory path",
                        "examples": [
                            "https://github.com/coderamp-labs/gitingest",
                            "/path/to/local/repo",
                            ".",
                        ],
                    },
                    "max_file_size": {
                        "type": "integer",
                        "description": "Maximum file size to process in bytes",
                        "default": 10485760,
                    },
                    "include_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Shell-style patterns to include",
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Shell-style patterns to exclude",
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch to clone and ingest",
                    },
                    "include_gitignored": {
                        "type": "boolean",
                        "description": "Include files matched by .gitignore",
                        "default": False,
                    },
                    "include_submodules": {
                        "type": "boolean",
                        "description": "Include repository's submodules",
                        "default": False,
                    },
                    "token": {
                        "type": "string",
                        "description": "GitHub personal access token for private repositories",
                    },
                },
                "required": ["source"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Execute a tool."""
    try:
        mcp_tool_calls_counter.labels(tool_name=name, status="started").inc()

        if name == "ingest_repository":
            result = await _handle_ingest_repository(arguments)
            mcp_tool_calls_counter.labels(tool_name=name, status="success").inc()
            return result

        mcp_tool_calls_counter.labels(tool_name=name, status="unknown_tool").inc()
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.exception("Error in tool call %s", name)
        mcp_tool_calls_counter.labels(tool_name=name, status="error").inc()
        return [TextContent(type="text", text=f"Error executing {name}: {e!s}")]


async def _handle_ingest_repository(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle repository ingestion."""
    try:
        source = arguments["source"]

        # Extract optional parameters
        max_file_size = arguments.get("max_file_size", 10485760)
        include_patterns = arguments.get("include_patterns")
        exclude_patterns = arguments.get("exclude_patterns")
        branch = arguments.get("branch")
        include_gitignored = arguments.get("include_gitignored", False)
        include_submodules = arguments.get("include_submodules", False)
        token = arguments.get("token")

        logger.info("Starting MCP ingestion", extra={"source": source})

        # Convert patterns to sets if provided
        include_patterns_set = set(include_patterns) if include_patterns else None
        exclude_patterns_set = set(exclude_patterns) if exclude_patterns else None

        # Call the ingestion function
        summary, tree, content = await ingest_async(
            source=source,
            max_file_size=max_file_size,
            include_patterns=include_patterns_set,
            exclude_patterns=exclude_patterns_set,
            branch=branch,
            include_gitignored=include_gitignored,
            include_submodules=include_submodules,
            token=token,
            output=None,  # Don't write to file, return content instead
        )

        # Create a structured response
        response_content = f"""# Repository Analysis: {source}

## Summary
{summary}

## File Structure
```
{tree}
```

## Content
{content}

---
*Generated by Gitingest MCP Server*
"""

        mcp_ingest_counter.labels(status="success").inc()
        return [TextContent(type="text", text=response_content)]

    except Exception as e:
        logger.exception("Error during ingestion")
        mcp_ingest_counter.labels(status="error").inc()
        return [TextContent(type="text", text=f"Error ingesting repository: {e!s}")]


async def start_mcp_server() -> None:
    """Start the MCP server with stdio transport."""
    logger.info("Starting Gitingest MCP server with stdio transport")
    await _run_stdio()


async def _run_stdio() -> None:
    """Run the MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )
