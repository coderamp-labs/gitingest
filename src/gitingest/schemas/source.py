"""Abstract base class for all source objects."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Source:
    """Base class for all sources (files, directories, etc)."""

    metadata: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)
