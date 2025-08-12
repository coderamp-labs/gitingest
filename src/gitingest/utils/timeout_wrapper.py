"""Utility functions for the Gitingest package."""

import asyncio
import functools
from collections.abc import Awaitable, Callable
from typing import TypeVar

from gitingest.utils.compat_typing import ParamSpec
from gitingest.utils.exceptions import AsyncTimeoutError

T = TypeVar("T")
P = ParamSpec("P")


def async_timeout(seconds: int) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Async Timeout decorator.

    This decorator wraps an asynchronous function and ensures it does not run for
    longer than the specified number of seconds. If the function execution exceeds
    this limit, it raises an ``AsyncTimeoutError``.

    Parameters
    ----------
    seconds : int
        The maximum allowed time (in seconds) for the asynchronous function to complete.

    Returns
    -------
    Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]
        A decorator that, when applied to an async function, ensures the function
        completes within the specified time limit. If the function takes too long,
        an ``AsyncTimeoutError`` is raised.

    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError as exc:
                msg = f"Operation timed out after {seconds} seconds"
                raise AsyncTimeoutError(msg) from exc

        return wrapper

    return decorator
