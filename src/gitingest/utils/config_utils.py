"""Configuration utilities."""

from __future__ import annotations

import os
import warnings


def _get_str_env_var(key: str, default: str) -> str:
    """Get string environment variable with ``GITINGEST_`` prefix and fallback to default.

    Parameters
    ----------
    key : str
        The name of the environment variable.
    default : str
        The default value to return if the environment variable is not set.

    Returns
    -------
    str
        The value of the environment variable.

    """
    value = os.environ.get(f"GITINGEST_{key}")

    if value is None:
        return default

    return value


def _get_int_env_var(key: str, default: int) -> int:
    """Get integer environment variable with ``GITINGEST_`` prefix and fallback to default.

    Parameters
    ----------
    key : str
        The name of the environment variable.
    default : int
        The default value to return if the environment variable is not set.

    Returns
    -------
    int
        The value of the environment variable as an integer.

    """
    try:
        return int(_get_str_env_var(key, default=str(default)))
    except ValueError:
        warnings.warn(f"Invalid value for GITINGEST_{key}. Using default: {default}", stacklevel=2)
        return default
