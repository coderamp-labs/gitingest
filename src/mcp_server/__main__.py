"""MCP server module entry point for running with python -m mcp_server."""

import asyncio
import click

# Import logging configuration first to intercept all logging
from gitingest.utils.logging_config import get_logger
from mcp_server.main import start_mcp_server_tcp

logger = get_logger(__name__)

@click.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "tcp"]),
    default="stdio",
    show_default=True,
    help="Transport protocol for MCP communication"
)
@click.option(
    "--host",
    default="0.0.0.0",
    show_default=True,
    help="Host to bind TCP server (only used with --transport tcp)"
)
@click.option(
    "--port",
    type=int,
    default=8001,
    show_default=True,
    help="Port for TCP server (only used with --transport tcp)"
)
def main(transport: str, host: str, port: int) -> None:
    """Start the Gitingest MCP (Model Context Protocol) server.
    
    The MCP server provides repository analysis capabilities to LLMs through
    the Model Context Protocol standard.
    
    Examples:
    
        # Start with stdio transport (default, for MCP clients)
        python -m mcp_server
        
        # Start with TCP transport for remote access
        python -m mcp_server --transport tcp --host 0.0.0.0 --port 8001
    """
    if transport == "tcp":
        # TCP mode needs asyncio
        asyncio.run(_async_main_tcp(host, port))
    else:
        # FastMCP stdio mode gère son propre event loop
        _main_stdio()

def _main_stdio() -> None:
    """Main function for stdio transport."""
    try:
        logger.info("Starting Gitingest MCP server with stdio transport")
        # FastMCP gère son propre event loop pour stdio
        from mcp_server.main import mcp
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as exc:
        logger.error(f"Error starting MCP server: {exc}", exc_info=True)
        raise click.Abort from exc

async def _async_main_tcp(host: str, port: int) -> None:
    """Async main function for TCP transport."""
    try:
        logger.info(f"Starting Gitingest MCP server with TCP transport on {host}:{port}")
        await start_mcp_server_tcp(host, port)
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as exc:
        logger.error(f"Error starting MCP server: {exc}", exc_info=True)
        raise click.Abort from exc

if __name__ == "__main__":
    main()
