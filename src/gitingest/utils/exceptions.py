"""Custom exceptions for the Gitingest package."""


class AsyncTimeoutError(Exception):
    """Exception raised when an async operation exceeds its timeout limit.

    This exception is used by the ``async_timeout`` decorator to signal that the wrapped
    asynchronous function has exceeded the specified time limit for execution.
    """


class InvalidNotebookError(Exception):
    """Exception raised when a Jupyter notebook is invalid or cannot be processed."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidGitHubTokenError(ValueError):
    """Exception raised when a GitHub Personal Access Token is malformed."""

    def __init__(self) -> None:
        msg = (
            "Invalid GitHub token format. To generate a token, go to "
            "https://github.com/settings/tokens/new?description=gitingest&scopes=repo."
        )
        super().__init__(msg)
