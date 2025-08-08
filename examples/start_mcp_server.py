#!/usr/bin/env python3
"""
Startup script for the Gitingest MCP server.

This script starts the MCP server with stdio transport.

Usage:
    python examples/start_mcp_server.py
"""

import sys
import asyncio
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from gitingest.mcp_server import start_mcp_server


async def main_wrapper():
    """Start the MCP server with stdio transport."""
    print("Starting Gitingest MCP Server")
    print("   Transport: stdio")
    print("   Mode: stdio (for MCP clients that support stdio transport)")
    
    print("\nServer Configuration:")
    print("   - Repository analysis and text digest generation")
    print("   - Token counting and file structure analysis")
    print("   - Support for both local directories and Git repositories")
    print()
    
    try:
        await start_mcp_server()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"\nError starting server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main_wrapper())