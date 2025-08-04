"""AI-powered ingestion flow with intelligent file selection."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import tiktoken

from gitingest.ingestion import ingest_query
from gitingest.output_formatter import format_node
from gitingest.schemas import FileSystemNode, FileSystemNodeType
from gitingest.utils.logging_config import get_logger
from server.ai_file_selector import get_ai_file_selector

if TYPE_CHECKING:
    from gitingest.schemas import IngestionQuery

# Initialize logger for this module
logger = get_logger(__name__)


class AIIngestResult:
    """Result of AI-powered ingestion."""
    
    def __init__(
        self,
        summary: str,
        tree: str,
        content: str,
        selected_files: list[str],
        reasoning: str,
    ):
        self.summary = summary
        self.tree = tree
        self.content = content
        self.selected_files = selected_files
        self.reasoning = reasoning


async def ai_ingest_query(
    query: IngestionQuery,
    user_prompt: str,
    context_size: str,
) -> AIIngestResult:
    """Run AI-powered ingestion with intelligent file selection.
    
    This implements the new flow:
    1. Run initial ingest to get file tree and content
    2. Use AI to select optimal files based on user prompt
    3. Re-run ingest with only selected files
    4. Crop to context window if needed
    """
    
    logger.info("Starting AI-powered ingestion", extra={
        "slug": query.slug,
        "user_prompt": user_prompt[:100] + "..." if len(user_prompt) > 100 else user_prompt,
        "context_size": context_size,
    })
    
    # Step 1: Run initial ingest to build full file tree and get sample content
    logger.info("Step 1: Running initial ingest for file discovery")
    initial_summary, initial_tree, initial_content = ingest_query(query)
    
    # Get root node for AI analysis
    root_node = _build_file_system_node(query)
    
    # Step 2: Use AI to select files (if AI is available)
    ai_selector = get_ai_file_selector()
    if ai_selector:
        logger.info("Step 2: Using AI for intelligent file selection")
        try:
            selection = await ai_selector.select_files(
                root_node=root_node,
                user_prompt=user_prompt,
                context_size=context_size,
                initial_content=initial_content,
            )
            selected_files = selection.selected_files
            reasoning = selection.reasoning
            
            logger.info("AI file selection completed", extra={
                "selected_files_count": len(selected_files),
            })
            
        except Exception as e:
            logger.warning("AI file selection failed, using fallback", extra={"error": str(e)})
            selected_files = _fallback_file_selection(root_node, context_size)
            reasoning = f"AI selection failed ({str(e)}), used fallback heuristics"
    else:
        logger.info("AI not available, using fallback file selection")
        selected_files = _fallback_file_selection(root_node, context_size)
        reasoning = "AI not configured, used fallback heuristics for file selection"
    
    # Step 3: Iteratively select files that fit within context size
    logger.info("Step 3: Fitting selected files within context size")
    final_content, final_tree, final_summary, final_selected_files = await _fit_files_to_context(
        query, selected_files, context_size
    )
    
    # Update summary with AI selection info
    enhanced_summary = _enhance_summary_with_ai_info(
        final_summary, len(final_selected_files), reasoning, context_size
    )
    
    logger.info("AI-powered ingestion completed successfully", extra={
        "final_files_count": len(final_selected_files),
        "final_content_length": len(final_content),
    })
    
    return AIIngestResult(
        summary=enhanced_summary,
        tree=final_tree,
        content=final_content,
        selected_files=final_selected_files,
        reasoning=reasoning,
    )


def _build_file_system_node(query: IngestionQuery) -> FileSystemNode:
    """Build a FileSystemNode tree for AI analysis without reading all content."""
    from gitingest.ingestion import _process_node
    from gitingest.schemas import FileSystemStats
    
    # Create root node
    path = query.local_path
    if query.subpath.strip("/"):
        path = path / query.subpath.strip("/")
    
    root_node = FileSystemNode(
        name=path.name,
        type=FileSystemNodeType.DIRECTORY,
        path_str=str(path.relative_to(query.local_path)),
        path=path,
    )
    
    # Process with limits to avoid reading too much content
    limited_query = query.model_copy()
    limited_query.max_file_size = min(query.max_file_size, 1024 * 1024)  # 1MB max per file
    
    stats = FileSystemStats()
    _process_node(node=root_node, query=limited_query, stats=stats)
    
    return root_node


def _fallback_file_selection(root_node: FileSystemNode, context_size: str) -> list[str]:
    """Fallback file selection using heuristics when AI is not available."""
    
    files = []
    _extract_files_recursive(root_node, files)
    
    # Prioritize important file types and names
    priority_files = []
    regular_files = []
    
    important_patterns = [
        r'README', r'main\.',  r'index\.', r'app\.', r'server\.', r'client\.',
        r'config\.', r'settings\.', r'package\.json', r'requirements\.txt',
        r'Dockerfile', r'docker-compose', r'\.env', r'makefile',
    ]
    
    important_extensions = {
        '.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb',
        '.php', '.cs', '.kt', '.swift', '.scala', '.sh', '.md', '.yml', '.yaml',
        '.json', '.xml', '.toml', '.ini'
    }
    
    for file_path in files:
        file_name = Path(file_path).name.lower()
        file_ext = Path(file_path).suffix.lower()
        
        is_important = any(
            __import__('re').search(pattern, file_name, __import__('re').IGNORECASE)
            for pattern in important_patterns
        )
        
        if is_important or file_ext in important_extensions:
            priority_files.append(file_path)
        else:
            regular_files.append(file_path)
    
    # Select based on context size
    context_limits = {
        "32k": 20,
        "128k": 50,
        "512k": 150,
        "1M": 300,
    }
    
    limit = context_limits.get(context_size, 50)
    
    # Combine priority and regular files
    selected = priority_files[:limit//2] + regular_files[:limit//2]
    return selected[:limit]


def _extract_files_recursive(node: FileSystemNode, files: list[str]) -> None:
    """Recursively extract file paths from node tree."""
    if node.type == FileSystemNodeType.FILE and node.path_str:
        files.append(node.path_str)
    elif node.type == FileSystemNodeType.DIRECTORY and hasattr(node, 'children'):
        for child in node.children:
            _extract_files_recursive(child, files)


async def _fit_files_to_context(
    query: IngestionQuery, 
    selected_files: list[str], 
    context_size: str
) -> tuple[str, str, str, list[str]]:
    """Iteratively add files until we reach the context size limit.
    
    Returns:
        tuple: (content, tree, summary, final_selected_files)
    """
    context_limit = _parse_context_size_to_tokens(context_size)
    
    # Start with an empty set and add files one by one
    final_selected_files = []
    current_content = ""
    current_tree = ""
    current_summary = ""
    
    logger.info("Fitting files to context", extra={
        "context_limit": context_limit,
        "candidate_files": len(selected_files)
    })
    
    for file_path in selected_files:
        # Try adding this file
        test_files = final_selected_files + [file_path]
        
        # Create a test query with these files
        test_query = _create_filtered_query(query, test_files)
        
        try:
            # Run ingestion with test files
            test_summary, test_tree, test_content = ingest_query(test_query)
            
            # Count tokens in the result
            combined_content = test_tree + "\n" + test_content
            token_count = _count_tokens_tiktoken(combined_content)
            
            if token_count <= context_limit:
                # This file fits, keep it
                final_selected_files = test_files
                current_content = test_content
                current_tree = test_tree
                current_summary = test_summary
                
                logger.debug("Added file to selection", extra={
                    "file": file_path,
                    "current_tokens": token_count,
                    "files_selected": len(final_selected_files)
                })
            else:
                # This file would exceed the limit, stop here
                logger.info("Reached context limit", extra={
                    "would_be_tokens": token_count,
                    "limit": context_limit,
                    "final_files": len(final_selected_files)
                })
                break
                
        except Exception as e:
            logger.warning("Failed to test file inclusion", extra={
                "file": file_path,
                "error": str(e)
            })
            # Skip this file and continue
            continue
    
    if not final_selected_files:
        # If no files fit, take at least the first one and crop it
        logger.warning("No files fit in context, taking first file and cropping")
        if selected_files:
            test_query = _create_filtered_query(query, [selected_files[0]])
            current_summary, current_tree, current_content = ingest_query(test_query)
            combined_content = current_tree + "\n" + current_content
            current_content = _crop_to_context_window(combined_content, context_size)
            final_selected_files = [selected_files[0]]
        else:
            # Fallback to empty response
            current_summary = "No files could be selected within context size"
            current_tree = "Empty repository structure"
            current_content = "No content available"
            final_selected_files = []
    
    return current_content, current_tree, current_summary, final_selected_files


def _count_tokens_tiktoken(text: str) -> int:
    """Count tokens using tiktoken."""
    try:
        encoding = tiktoken.get_encoding("o200k_base")
        return len(encoding.encode(text, disallowed_special=()))
    except Exception:
        # Fallback to character-based estimation
        return len(text) // 4


def _create_filtered_query(query: IngestionQuery, selected_files: list[str]) -> IngestionQuery:
    """Create a new query that includes only the selected files."""
    
    # Convert selected files to include patterns
    include_patterns = set(selected_files)
    
    filtered_query = query.model_copy()
    filtered_query.include_patterns = include_patterns
    filtered_query.ignore_patterns = set()  # Clear ignore patterns since we have explicit includes
    
    return filtered_query


def _crop_to_context_window(content: str, context_size: str) -> str:
    """Crop content to fit within the specified context window."""
    
    try:
        encoding = tiktoken.get_encoding("o200k_base")
        tokens = encoding.encode(content, disallowed_special=())
    except Exception:
        # Fallback to character-based estimation
        tokens = [0] * (len(content) // 4)  # Rough estimate: 4 chars per token
    
    # Parse context size to get token limit
    limit = _parse_context_size_to_tokens(context_size)
    
    if len(tokens) <= limit:
        return content
    
    # Crop tokens and decode back to text
    try:
        cropped_tokens = tokens[:limit]
        cropped_content = encoding.decode(cropped_tokens)
        
        # Add truncation notice
        truncation_notice = f"\n\n[Content truncated to {context_size} token limit]"
        return cropped_content + truncation_notice
        
    except Exception:
        # Fallback to character-based cropping
        char_limit = limit * 4  # Rough estimate
        if len(content) <= char_limit:
            return content
        
        cropped = content[:char_limit]
        truncation_notice = f"\n\n[Content truncated to approximately {context_size} tokens]"
        return cropped + truncation_notice


def _parse_context_size_to_tokens(context_size: str) -> int:
    """Parse context size string to token count."""
    # Predefined sizes
    size_map = {
        "32k": 32_000,
        "128k": 128_000,
        "512k": 512_000,
        "1M": 1_000_000,
    }
    
    # Check predefined sizes first
    if context_size in size_map:
        return size_map[context_size]
    
    # Parse custom sizes
    context_size_lower = context_size.lower().strip()
    
    try:
        if context_size_lower.endswith('k'):
            # Handle "250k", "32k", etc.
            num_str = context_size_lower[:-1]
            return int(float(num_str) * 1_000)
        elif context_size_lower.endswith('m'):
            # Handle "1M", "1.5M", etc.
            num_str = context_size_lower[:-1]
            return int(float(num_str) * 1_000_000)
        elif context_size_lower.isdigit():
            # Handle plain numbers as tokens
            return int(context_size_lower)
        else:
            logger.warning(f"Invalid context size format: {context_size}, using default 128k")
            return 128_000
    except (ValueError, TypeError):
        logger.warning(f"Failed to parse context size: {context_size}, using default 128k")
        return 128_000


def _enhance_summary_with_ai_info(
    original_summary: str,
    selected_files_count: int,
    reasoning: str,
    context_size: str,
) -> str:
    """Enhance the summary with AI selection information."""
    
    ai_info = f"""
Selected Files: {selected_files_count}
Context Size: {context_size} tokens
Selection Reasoning: {reasoning}

{original_summary}"""
    
    return ai_info.strip()