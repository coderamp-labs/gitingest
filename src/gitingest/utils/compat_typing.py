"""Compatibility layer for typing."""

try:
    from enum import StrEnum  # type: ignore[attr-defined]  # Py ≥ 3.11
except ImportError:
    from strenum import StrEnum  # type: ignore[import-untyped] # Py ≤ 3.10

try:
    from typing import ParamSpec, TypeAlias  # type: ignore[attr-defined]  # Py ≥ 3.10
except ImportError:
    from typing_extensions import ParamSpec, TypeAlias  # type: ignore[attr-defined]  # Py ≤ 3.9

try:
    from typing import Annotated  # type: ignore[attr-defined]  # Py ≥ 3.9
except ImportError:
    from typing_extensions import Annotated  # type: ignore[attr-defined]  # Py ≤ 3.8

__all__ = ["Annotated", "ParamSpec", "StrEnum", "TypeAlias"]
