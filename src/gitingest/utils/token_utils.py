"""Optimized token counting utilities with memory management."""

from __future__ import annotations

import gc
import os
from typing import Protocol, Self

from gitingest.utils.logging_config import get_logger

# Try to import tiktoken, but don't fail if it's not available
try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    tiktoken = None  # type: ignore[assignment]
    TIKTOKEN_AVAILABLE = False

logger = get_logger(__name__)

# Environment variable to disable token counting for memory-sensitive environments
DISABLE_TOKEN_COUNTING = os.getenv("GITINGEST_DISABLE_TOKEN_COUNTING", "false").lower() == "true"

# Constants for token formatting
TOKEN_MILLION = 1_000_000
TOKEN_THOUSAND = 1_000


class Encoding(Protocol):
    """Protocol for tiktoken encoding objects."""

    def encode(self, text: str, *, disallowed_special: tuple[str, ...] = ()) -> list[int]:
        """Encode text to tokens."""


class TokenEncoder:
    """Singleton class to manage token encoding with lazy loading."""

    _instance: TokenEncoder | None = None
    _encoding: Encoding | None = None

    def __new__(cls) -> Self:
        """Create or return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_encoding(self) -> Encoding | None:
        """Get or create a cached encoding instance.

        Returns
        -------
        Encoding | None
            The cached encoding instance, or None if token counting is disabled

        """
        if DISABLE_TOKEN_COUNTING:
            return None

        if self._encoding is None:
            self._encoding = self._load_encoding()
        return self._encoding

    def _load_encoding(self) -> Encoding | None:
        """Load the tiktoken encoding.

        Returns
        -------
        Encoding | None
            The encoding instance or None if tiktoken is not available

        """
        if not TIKTOKEN_AVAILABLE:
            logger.warning("tiktoken not available, token counting disabled")
            return None

        try:
            return tiktoken.get_encoding("o200k_base")  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning("Failed to load tiktoken encoding", extra={"error": str(exc)})
            return None

    def clear_cache(self) -> None:
        """Clear the encoding cache to free memory."""
        if self._encoding is not None:
            self._encoding = None
            gc.collect()


# Create the singleton instance
_token_encoder = TokenEncoder()


def get_cached_encoding() -> Encoding | None:
    """Get or create a cached encoding instance.

    Returns
    -------
    Encoding | None
        The cached encoding instance, or None if token counting is disabled

    """
    return _token_encoder.get_encoding()


def clear_encoding_cache() -> None:
    """Clear the global encoding cache to free memory."""
    _token_encoder.clear_cache()


def count_tokens_optimized(text: str, chunk_size: int = 100000) -> int:
    """Count tokens with memory optimization.

    Parameters
    ----------
    text : str
        Text to count tokens for
    chunk_size : int
        Size of chunks to process at a time (default: 100k chars)

    Returns
    -------
    int
        Total token count, or estimated count if token counting is disabled

    """
    # If token counting is disabled, return a rough estimate
    if DISABLE_TOKEN_COUNTING:
        # Rough estimate: ~1.3 tokens per character for code
        return int(len(text) * 1.3)

    try:
        encoding = get_cached_encoding()
        if encoding is None:
            # Fallback to estimation
            return int(len(text) * 1.3)

        # Process in chunks to avoid memory spike for large texts
        total_tokens = 0

        if len(text) > chunk_size:
            # Process large texts in chunks
            for i in range(0, len(text), chunk_size):
                chunk = text[i : i + chunk_size]
                tokens = encoding.encode(chunk, disallowed_special=())
                total_tokens += len(tokens)
                # Clear the tokens list immediately to free memory
                del tokens
        else:
            tokens = encoding.encode(text, disallowed_special=())
            total_tokens = len(tokens)
            del tokens

    except (ValueError, UnicodeEncodeError) as exc:
        logger.warning("Failed to count tokens", extra={"error": str(exc)})
        return int(len(text) * 1.3)  # Fallback to estimation
    except Exception as exc:
        logger.warning("Unexpected error counting tokens", extra={"error": str(exc)})
        return int(len(text) * 1.3)  # Fallback to estimation

    return total_tokens


def format_token_count(count: int) -> str:
    """Format token count as human-readable string.

    Parameters
    ----------
    count : int
        Token count

    Returns
    -------
    str
        Formatted string (e.g., "1.2k", "1.2M")

    """
    if count >= TOKEN_MILLION:
        return f"{count / TOKEN_MILLION:.1f}M"
    if count >= TOKEN_THOUSAND:
        return f"{count / TOKEN_THOUSAND:.1f}k"
    return str(count)
