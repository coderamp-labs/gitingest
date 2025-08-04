# Gitingest Codebase Architecture Documentation

## Overview

Gitingest is a Python-based tool that transforms Git repositories into prompt-friendly text digests for Large Language Models (LLMs). The project consists of two main components: a command-line interface (CLI) and a web server with REST API, both sharing the same core ingestion engine.

## Project Structure

```
gitingest/
├── src/
│   ├── gitingest/           # Core CLI package
│   │   ├── __main__.py      # CLI entry point
│   │   ├── entrypoint.py    # Main ingestion functions
│   │   ├── ingestion.py     # File system processing
│   │   ├── query_parser.py  # URL/path parsing
│   │   ├── clone.py         # Git repository cloning
│   │   ├── config.py        # Configuration constants
│   │   ├── output_formatter.py # Output formatting
│   │   ├── schemas/         # Pydantic data models
│   │   └── utils/           # Utility functions
│   ├── server/              # FastAPI web server
│   │   ├── __main__.py      # Server entry point
│   │   ├── main.py          # FastAPI app configuration
│   │   ├── routers/         # API endpoints
│   │   ├── templates/       # Jinja2 HTML templates
│   │   └── models.py        # Server-specific models
│   └── static/              # Web assets (CSS, JS, images)
├── tests/                   # Test suite
├── pyproject.toml          # Project configuration
└── docker-compose.yml     # Container orchestration
```

## Core Architecture

### 1. Entry Points

The application has two main entry points:

- **CLI**: `src/gitingest/__main__.py` - Command-line interface using Click
- **Server**: `src/server/__main__.py` - Web server using FastAPI and Uvicorn

### 2. Core Processing Flow

The ingestion process follows this high-level flow:

```
Input (URL/Path) → Query Parsing → Repository Cloning → File Processing → Output Formatting
```

#### Detailed Flow:

1. **Input Processing** (`entrypoint.py:ingest_async`)
   - Accepts local directory paths or Git repository URLs
   - Resolves authentication tokens from environment or parameters
   - Determines if input is local or remote

2. **Query Parsing** (`query_parser.py`)
   - **Remote repositories**: `parse_remote_repo()` handles GitHub/GitLab/etc URLs
   - **Local directories**: `parse_local_dir_path()` processes file system paths
   - Creates `IngestionQuery` object with all necessary metadata

3. **Repository Cloning** (`clone.py`)
   - Only for remote repositories
   - Uses Git CLI with optimized flags for performance
   - Supports partial clones, specific branches/tags/commits
   - Handles authentication via GitHub tokens
   - Creates temporary directories managed via context managers

4. **File System Processing** (`ingestion.py`)
   - Traverses directory structure respecting limits and patterns
   - Applies `.gitignore` and `.gitingestignore` filtering
   - Reads file contents with size limits
   - Builds hierarchical `FileSystemNode` tree structure

5. **Output Formatting** (`output_formatter.py`)
   - Generates summary with repository metadata
   - Creates tree-style directory structure visualization
   - Concatenates all file contents
   - Estimates token count using tiktoken library

### 3. Data Models

The codebase uses Pydantic for data validation and modeling:

#### Core Models (`schemas/ingestion.py`):
- **`IngestionQuery`**: Central data structure containing all processing parameters
- **`FileSystemNode`**: Represents files/directories with metadata and content
- **`CloneConfig`**: Git cloning configuration extracted from IngestionQuery

#### Server Models (`server/models.py`):
- **`IngestRequest`**: API request validation for web endpoints

### 4. Configuration System

Configuration is centralized in `config.py`:

```python
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file
MAX_DIRECTORY_DEPTH = 20          # Directory traversal depth
MAX_FILES = 10_000                # Total file count limit
MAX_TOTAL_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB total output
```

## Component Deep Dive

### CLI Component (`src/gitingest/`)

#### Entry Point (`__main__.py`)
- Uses Click framework for command-line argument parsing
- Supports various options: file size limits, include/exclude patterns, output destinations
- Handles both local paths and remote URLs
- Provides comprehensive help and examples

#### Core Functions (`entrypoint.py`)
- **`ingest_async()`**: Main asynchronous ingestion function
- **`ingest()`**: Synchronous wrapper for library usage
- Manages temporary directory lifecycle for cloned repositories
- Handles authentication token resolution

#### Query Processing (`query_parser.py`)
- **URL Parsing**: Handles GitHub, GitLab, and other Git hosting services
- **Branch/Tag Resolution**: Fetches remote references to validate branches/tags
- **Subpath Support**: Processes URLs pointing to specific directories or files
- **Commit Hash Detection**: Identifies and validates Git commit hashes

#### Git Operations (`clone.py`)
- **Repository Validation**: Checks if repositories exist and are accessible
- **Optimized Cloning**: Uses `--single-branch`, `--depth=1`, and sparse checkout
- **Authentication**: Integrates GitHub tokens for private repository access
- **Submodule Support**: Recursively clones submodules when requested

#### File Processing (`ingestion.py`)
- **Recursive Traversal**: Walks directory trees with configurable depth limits
- **Pattern Matching**: Applies include/exclude patterns using `pathspec` library
- **Content Reading**: Safely reads file contents with encoding detection
- **Resource Management**: Enforces limits on file count, size, and total output

### Server Component (`src/server/`)

#### FastAPI Application (`main.py`)
- **Middleware**: TrustedHost, rate limiting, CORS handling
- **Monitoring**: Optional Sentry integration for error tracking
- **Metrics**: Prometheus metrics server for observability
- **Static Files**: Serves CSS, JavaScript, and image assets

#### API Endpoints (`routers/`)

##### Ingest Router (`routers/ingest.py`)
- **POST `/api/ingest`**: Primary ingestion endpoint accepting JSON requests
- **GET `/api/{user}/{repository}`**: GitHub-specific shorthand endpoint
- **GET `/api/download/file/{ingest_id}`**: Download processed files (when S3 disabled)
- Rate limiting: 10 requests per minute per IP
- Prometheus metrics collection

##### Index Router (`routers/index.py`)
- **GET `/`**: Home page with example repositories and form interface
- Uses Jinja2 templates for server-side rendering

##### Dynamic Router (`routers/dynamic.py`)
- **GET `/{user}/{repository}`**: GitHub repository processing via URL path
- Mirrors GitHub's URL structure for intuitive usage

#### Templates (`templates/`)
- **Jinja2 Templates**: Server-side rendered HTML pages
- **Tailwind CSS**: Utility-first CSS framework for styling
- **Component Architecture**: Reusable template components and macros

### Utility Modules (`src/gitingest/utils/`)

#### Authentication (`auth.py`)
- GitHub token resolution from environment variables or parameters
- Token validation and format checking

#### Git Utilities (`git_utils.py`)
- Git command execution with proper error handling
- Remote repository validation and branch/tag fetching
- Commit resolution and validation

#### File Operations (`file_utils.py`)
- Safe file reading with encoding detection
- Binary file detection and handling
- File system utilities and path operations

#### Pattern Matching (`pattern_utils.py`, `ignore_patterns.py`)
- `.gitignore` and `.gitingestignore` parsing
- Glob pattern processing and matching
- Include/exclude pattern application

## Key Features

### 1. Multiple Input Sources
- **Local Directories**: Direct file system processing
- **Git URLs**: GitHub, GitLab, Bitbucket, and custom Git servers
- **Subpaths**: Process specific directories within repositories
- **Branches/Tags/Commits**: Target specific repository states

### 2. Flexible Filtering
- **Pattern Matching**: Include/exclude files using glob patterns
- **Gitignore Support**: Respects `.gitignore` and `.gitingestignore` files
- **File Size Limits**: Configurable per-file and total size limits
- **Directory Depth**: Prevents infinite recursion in deep structures

### 3. Output Formats
- **Summary Section**: Repository metadata, file counts, token estimates
- **Directory Tree**: Visual file structure representation
- **File Contents**: Concatenated file contents with clear delimiters
- **Token Estimation**: Uses tiktoken for LLM token counting

### 4. Performance Optimizations
- **Asynchronous Operations**: Non-blocking I/O for network and file operations
- **Sparse Git Clones**: Minimal data transfer for large repositories
- **Streaming Processing**: Memory-efficient file processing
- **Caching**: Intelligent caching of Git operations and file reads

### 5. Security Features
- **Path Validation**: Prevents directory traversal attacks
- **Input Sanitization**: Validates all user inputs
- **Token Handling**: Secure GitHub token management
- **Resource Limits**: Prevents DoS through resource exhaustion

## Development and Deployment

### Environment Setup
- **Python 3.8+**: Modern Python with type hints and async support
- **Dependencies**: Managed via `pyproject.toml` with optional extras
- **Development Tools**: pytest, ruff, pre-commit hooks

### Docker Support
- **Multi-stage Builds**: Optimized container images
- **Docker Compose**: Development and production environments
- **MinIO Integration**: S3-compatible storage for development

### Configuration Management
- **Environment Variables**: Extensive configuration via env vars
- **Default Values**: Sensible defaults for all settings
- **Validation**: Pydantic-based configuration validation

### Monitoring and Observability
- **Structured Logging**: JSON-formatted logs with contextual information
- **Metrics Collection**: Prometheus metrics for API endpoints
- **Error Tracking**: Optional Sentry integration
- **Health Checks**: Built-in health and readiness endpoints

## Integration Points

### API Integration
- **REST API**: Full-featured API for programmatic access
- **OpenAPI/Swagger**: Auto-generated API documentation
- **JSON Responses**: Structured responses with consistent error handling

### Library Usage
- **Python Package**: Available on PyPI for direct import
- **Async/Sync APIs**: Both `ingest_async()` and `ingest()` functions
- **Type Hints**: Full type annotation support

### Browser Extensions
- **Chrome/Firefox Extensions**: Direct integration with GitHub UI
- **URL Transformation**: Seamless conversion from GitHub URLs

## Security Considerations

### Input Validation
- **URL Parsing**: Strict validation of repository URLs
- **Path Sanitization**: Prevention of directory traversal
- **Pattern Validation**: Safe handling of glob patterns

### Authentication
- **Token Security**: Secure GitHub token handling
- **Access Control**: Respects repository visibility settings
- **Rate Limiting**: Protection against abuse

### Resource Management
- **Memory Limits**: Bounded memory usage for large repositories
- **Timeout Controls**: Prevents hanging operations
- **Cleanup**: Automatic cleanup of temporary files

This architecture provides a robust, scalable, and secure foundation for converting Git repositories into LLM-friendly text formats, with clear separation of concerns and extensive configurability.