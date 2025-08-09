"""AI-powered ingestion flow with intelligent file selection."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import tiktoken

from gitingest.ingestion import ingest_query
from gitingest.output_formatter import format_node
from gitingest.schemas import FileSystemNode, FileSystemNodeType
from gitingest.utils.compat_func import readlink
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
        selected_files: list[str],  # List of selected file paths
        selected_files_detailed: dict[str, dict] | None,  # Detailed info with reasoning
        reasoning: str,
    ):
        self.summary = summary
        self.tree = tree
        self.content = content
        self.selected_files = selected_files
        self.selected_files_detailed = selected_files_detailed
        self.reasoning = reasoning


async def ai_ingest_query(
    root_node: FileSystemNode,
    query: IngestionQuery,
    user_prompt: str,
    context_size: str,
    initial_content: str,
) -> AIIngestResult:
    """Apply AI scoring to an existing file tree and generate digest.
    
    Takes an existing file tree and applies AI likelihood scores to it,
    then generates a digest using the existing mechanism.
    """
    
    logger.info("Starting AI-powered file scoring", extra={
        "slug": query.slug,
        "user_prompt": user_prompt[:100] + "..." if len(user_prompt) > 100 else user_prompt,
        "context_size": context_size,
    })
    
    # Apply AI scoring to the existing tree
    ai_selector = get_ai_file_selector()
    selected_files_detailed = None
    selected_files = []
    if ai_selector:
        logger.info("Calling Gemini for file scoring")
        try:
            ai_response = await ai_selector.select_files(
                root_node=root_node,
                user_prompt=user_prompt,
                context_size=context_size,
                initial_content=initial_content,
            )
            reasoning = ai_response.reasoning
            selected_files_detailed = ai_response.selected_files_detailed
            selected_files = ai_response.selected_files
            
        except Exception as e:
            logger.warning("AI file scoring failed, using fallback", extra={"error": str(e)})
            _set_fallback_scores(root_node)
            reasoning = f"AI scoring failed ({str(e)}), used fallback scoring"
            # Extract all files with scores > 0 as fallback
            selected_files = _extract_files_above_threshold(root_node, 0)
    else:
        logger.info("AI not available, using fallback scoring")
        _set_fallback_scores(root_node)
        reasoning = "AI not configured, used fallback scoring"
        # Extract all files with scores > 0 as fallback
        selected_files = _extract_files_above_threshold(root_node, 0)
    
    logger.info("Files selected after AI scoring", extra={
        "selected_count": len(selected_files)
    })
    
    # Generate digest using existing mechanism
    logger.info("Generating digest with AI-selected files")
    
    # Parse context size to tokens for optimization
    context_tokens = _parse_context_size_to_tokens(context_size)
    
    # Use context-aware formatting instead of regular ingestion
    from gitingest.output_formatter import format_node_with_context_limit
    final_summary, final_tree, final_content = format_node_with_context_limit(
        root_node, query, context_tokens
    )
    final_selected_files = selected_files
    
    # Update summary with AI selection info
    enhanced_summary = _enhance_summary_with_ai_info(
        final_summary, len(final_selected_files), reasoning, context_size
    )
    
    logger.info("AI-powered ingestion completed successfully", extra={
        "final_files_count": len(final_selected_files),
        "final_content_length": len(final_content)
    })
    
    return AIIngestResult(
        summary=enhanced_summary,
        tree=final_tree,
        content=final_content,
        selected_files=final_selected_files,
        selected_files_detailed=selected_files_detailed,
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


def _set_fallback_scores(node: FileSystemNode) -> None:
    """Set fallback scores for files when AI is not available."""
    if node.type == FileSystemNodeType.FILE:
        # Use heuristics to score files
        file_name = node.name.lower()
        file_ext = Path(node.path_str).suffix.lower() if node.path_str else ""
        
        # High importance files
        if any(pattern in file_name for pattern in ['readme', 'main', 'index', 'app', 'server']):
            node.likelihood_score = 90
        # Important extensions
        elif file_ext in {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs'}:
            node.likelihood_score = 70
        # Config files
        elif file_ext in {'.json', '.yaml', '.yml', '.toml', '.ini', '.env'}:
            node.likelihood_score = 60
        # Documentation
        elif file_ext in {'.md', '.txt', '.rst'}:
            node.likelihood_score = 50
        # Other files
        else:
            node.likelihood_score = 30
    
    # Recursively process children
    if node.type == FileSystemNodeType.DIRECTORY and hasattr(node, 'children'):
        for child in node.children:
            _set_fallback_scores(child)


def _extract_files_above_threshold(node: FileSystemNode, threshold: int) -> list[str]:
    """Extract file paths that have likelihood scores above the threshold."""
    files = []
    
    def _collect_files(n: FileSystemNode) -> None:
        if n.type == FileSystemNodeType.FILE and n.path_str:
            if n.likelihood_score > threshold:
                files.append(n.path_str)
        elif n.type == FileSystemNodeType.DIRECTORY and hasattr(n, 'children'):
            for child in n.children:
                _collect_files(child)
    
    _collect_files(node)
    return files


def _extract_files_recursive(node: FileSystemNode, files: list[str]) -> None:
    """Recursively extract file paths from node tree."""
    if node.type == FileSystemNodeType.FILE and node.path_str:
        files.append(node.path_str)
    elif node.type == FileSystemNodeType.DIRECTORY and hasattr(node, 'children'):
        for child in node.children:
            _extract_files_recursive(child, files)



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