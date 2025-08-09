# Gitingest MCP Server

Gitingest includes an MCP (Model Context Protocol) server that allows LLMs to directly access repository analysis capabilities through the MCP protocol.

## What is MCP?

The Model Context Protocol (MCP) is a standardized protocol that enables language models to interact with external tools and resources in a structured manner. It facilitates the integration of specialized capabilities into LLM workflows.

## Installation

To use the MCP server, install Gitingest with MCP dependencies:

```bash
pip install gitingest[mcp]
```

## Starting the MCP Server

### Stdio Transport (Default)

```bash
gitingest --mcp-server
```

The MCP server uses stdio for communication by default, making it compatible with all MCP clients.


## Available Tools

### `ingest_repository`

Ingests a Git repository or local directory and returns a structured digest.

**Parameters:**
- `source` (required): Git repository URL or local directory path
- `max_file_size` (optional): Maximum file size in bytes (default: 10485760)
- `include_patterns` (optional): Shell patterns to include files
- `exclude_patterns` (optional): Shell patterns to exclude files
- `branch` (optional): Git branch to clone and ingest
- `include_gitignored` (optional): Include files ignored by .gitignore (default: false)
- `include_submodules` (optional): Include Git submodules (default: false)
- `token` (optional): GitHub personal access token for private repositories

**Usage example:**
```json
{
  "source": "https://github.com/coderamp-labs/gitingest",
  "max_file_size": 1048576,
  "include_patterns": ["*.py", "*.md"],
  "exclude_patterns": ["tests/*"]
}
```

## MCP Client Configuration

### Stdio Transport Configuration

Create a configuration file for your MCP client:

```json
{
  "mcpServers": {
    "gitingest": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```


### Environment Variables

- `GITHUB_TOKEN`: GitHub personal access token for private repositories

## Integration Examples

### Python Client Examples

See the following examples for how to use the Gitingest MCP server:

- **`examples/mcp_client_example.py`** - Stdio transport example
- **`examples/start_mcp_server.py`** - Startup script for stdio transport

### Integration with Claude Desktop

1. Install Gitingest with MCP dependencies
2. Create an MCP configuration file in your Claude configuration directory
3. Restart Claude Desktop
4. Use Gitingest tools in your conversations

### Integration with Other MCP Clients

The Gitingest MCP server is compatible with all MCP-compliant clients. Consult your MCP client's documentation for specific integration instructions.

## Output Format

The MCP server returns structured content that includes:

1. **Summary**: General information about the repository
2. **File Structure**: Tree structure of files and directories
3. **Content**: Code file content with LLM-optimized formatting

## Error Handling

The MCP server handles errors gracefully and returns informative error messages. Common errors include:

- Private repositories without authentication token
- Invalid repository URLs
- Network issues during cloning
- Files that are too large

## Limitations

- The MCP server does not maintain a cache of ingested repositories (future feature)
- Persistent resources are not yet implemented
- The server uses stdio transport for MCP communication

## Development

To contribute to the MCP server:

1. Consult the MCP specification: https://modelcontextprotocol.io/
2. Tests are located in `tests/test_mcp_server.py`
3. The client example is located in `examples/mcp_client_example.py`

## Support

For help with the MCP server:

- Consult the official MCP documentation
- Open an issue on GitHub
- Join the Discord community
