"""AI-based file selection service using Google Gemini."""

from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING

import google.generativeai as genai
import tiktoken
from pydantic import BaseModel

from gitingest.utils.logging_config import get_logger

if TYPE_CHECKING:
    from gitingest.schemas import FileSystemNode

# Initialize logger for this module
logger = get_logger(__name__)


class FileSelectionResponse(BaseModel):
    """Response model for AI file selection."""
    
    selected_files: list[str]
    reasoning: str


class AIFileSelector:
    """AI-powered file selection service using Google Gemini."""
    
    def __init__(self):
        """Initialize the AI file selector with Gemini API."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-pro")
        self.encoding = tiktoken.get_encoding("o200k_base")
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        try:
            return len(self.encoding.encode(text, disallowed_special=()))
        except Exception:
            # Fallback to character-based estimation if tiktoken fails
            return len(text) // 4
    
    def _create_file_summary(self, node: FileSystemNode, base_path: str = "") -> dict:
        """Create a hierarchical summary of files with sizes and paths."""
        summary = {
            "path": node.path_str or base_path,
            "type": node.type.value,
            "size": node.size if hasattr(node, 'size') else 0,
        }
        
        if node.type.value == "directory" and node.children:
            summary["children"] = [
                self._create_file_summary(child, node.path_str or base_path)
                for child in node.children
            ]
            summary["total_files"] = node.file_count if hasattr(node, 'file_count') else len([
                c for c in node.children if c.type.value == "file"
            ])
        elif node.type.value == "file" and hasattr(node, 'content'):
            # Add content preview for better AI understanding
            content_preview = node.content[:500] if node.content else ""
            summary["content_preview"] = content_preview
            summary["lines"] = len(node.content.splitlines()) if node.content else 0
        
        return summary
    
    def _extract_context_size_tokens(self, context_size: str) -> int:
        """Convert context size string to token count."""
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
    
    def _create_selection_prompt(
        self,
        file_summary: dict,
        user_prompt: str,
        context_size_tokens: int,
        content_sample: str,
    ) -> str:
        """Create the prompt for AI file selection."""
        
        default_prompt = (
            "Generate a useful and comprehensive code digest that would be helpful "
            "for understanding the codebase structure, main functionality, and key components."
        )
        
        effective_prompt = user_prompt.strip() if user_prompt.strip() else default_prompt
        
        return f"""You are an expert code analyst helping to create an optimal digest of a codebase for Large Language Models.

TASK:
Select the most relevant files from this codebase to create a {context_size_tokens:,} token digest that best serves this purpose:
"{effective_prompt}"

REPOSITORY STRUCTURE:
{json.dumps(file_summary, indent=2)}

CONTENT SAMPLE (first ~1M tokens):
{content_sample}

CONSTRAINTS:
- Target exactly {context_size_tokens:,} tokens in the final output
- Prioritize files that are most relevant to the user's request
- Include key architectural files (main entry points, configuration, core modules)
- Balance breadth (overview) with depth (important details)
- Avoid redundant or duplicate content
- Consider file dependencies and relationships

RESPONSE FORMAT:
Return a JSON object with this exact structure:
{{
    "selected_files": [
        "path/to/file1.py",
        "path/to/file2.js",
        "path/to/file3.md"
    ],
    "reasoning": "Brief explanation of why these files were selected and how they serve the user's request."
}}

Only return the JSON object, no other text."""

    async def select_files(
        self,
        root_node: FileSystemNode,
        user_prompt: str,
        context_size: str,
        initial_content: str,
    ) -> FileSelectionResponse:
        """Select optimal files using AI based on user prompt and context size."""
        
        logger.info("Starting AI file selection", extra={
            "user_prompt": user_prompt[:100] + "..." if len(user_prompt) > 100 else user_prompt,
            "context_size": context_size,
            "content_length": len(initial_content)
        })
        
        context_size_tokens = self._extract_context_size_tokens(context_size)
        
        # Create file structure summary
        file_summary = self._create_file_summary(root_node)
        
        # Limit content sample to ~1M tokens
        max_sample_tokens = 1_000_000
        if self._count_tokens(initial_content) > max_sample_tokens:
            # Truncate content to fit in ~1M tokens (leave some margin)
            estimated_chars = max_sample_tokens * 4  # rough estimate
            content_sample = initial_content[:estimated_chars]
            logger.info("Truncated content sample for AI analysis", extra={
                "original_tokens": self._count_tokens(initial_content),
                "sample_tokens": self._count_tokens(content_sample)
            })
        else:
            content_sample = initial_content
        
        # Create selection prompt
        prompt = self._create_selection_prompt(
            file_summary, user_prompt, context_size_tokens, content_sample
        )
        
        try:
            # Call Gemini API
            logger.info("Calling Gemini API for file selection")
            response = await self.model.generate_content_async(prompt)
            
            if not response.text:
                raise ValueError("Empty response from Gemini API")
            
            # Parse JSON response
            response_text = response.text.strip()
            
            # Extract JSON from response (handle cases where AI adds extra text)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            else:
                json_text = response_text
            
            try:
                parsed_response = json.loads(json_text)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON response, attempting to extract files manually")
                # Fallback: try to extract file paths from response
                file_paths = re.findall(r'"([^"]+\.[a-zA-Z]+)"', response_text)
                parsed_response = {
                    "selected_files": file_paths,
                    "reasoning": "Extracted files from AI response (JSON parsing failed)"
                }
            
            selection = FileSelectionResponse(
                selected_files=parsed_response.get("selected_files", []),
                reasoning=parsed_response.get("reasoning", "No reasoning provided")
            )
            
            logger.info("AI file selection completed", extra={
                "selected_files_count": len(selection.selected_files),
                "reasoning_length": len(selection.reasoning)
            })
            
            return selection
            
        except Exception as e:
            logger.error("AI file selection failed", extra={"error": str(e)})
            # Fallback: return all files up to a reasonable limit
            all_files = self._extract_all_files(root_node)
            return FileSelectionResponse(
                selected_files=all_files[:50],  # Limit to 50 files as fallback
                reasoning=f"AI selection failed ({str(e)}), using fallback selection of key files"
            )
    
    def _extract_all_files(self, node: FileSystemNode, files: list[str] | None = None) -> list[str]:
        """Extract all file paths from the node tree."""
        if files is None:
            files = []
        
        if node.type.value == "file" and node.path_str:
            files.append(node.path_str)
        elif node.type.value == "directory" and hasattr(node, 'children'):
            for child in node.children:
                self._extract_all_files(child, files)
        
        return files


def get_ai_file_selector() -> AIFileSelector | None:
    """Get AI file selector instance, return None if not configured."""
    try:
        return AIFileSelector()
    except ValueError as e:
        logger.warning("AI file selector not available", extra={"error": str(e)})
        return None