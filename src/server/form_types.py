"""Reusable form type aliases for FastAPI form parameters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Form

from gitingest.utils.compat_typing import Annotated

if TYPE_CHECKING:
    from gitingest.utils.compat_typing import TypeAlias

StrForm: TypeAlias = Annotated[str, Form(...)]
IntForm: TypeAlias = Annotated[int, Form(...)]
OptStrForm: TypeAlias = Annotated[str | None, Form()]
