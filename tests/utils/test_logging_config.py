"""Regression tests for InterceptHandler's frame walker.

The positive test pins the fix: intercepted records are attributed to
the actual originating caller.

The negative test pins the original
bug: with the pre-fix frame walker, every record collapses to stdlib
Logger.callHandlers so a future regression reintroduces a
detectable failure mode.
"""

import logging

import pytest

# configure_logging() runs at module scope on import, installs
# gitingest's InterceptHandler globally.
from gitingest.utils import logging_config


def test_intercept_handler_attributes_to_caller() -> None:
    """Intercepted record is attributed to the actual caller."""
    captured: dict = {}
    sink_id = logging_config.logger.add(
        lambda msg: captured.update(msg.record),
        level=0,
        format="{message}",
    )
    try:
        logging.getLogger("demo").error("ping")
    finally:
        logging_config.logger.remove(sink_id)

    # Bug renders this as function="callHandlers" (stdlib internal)
    # or "<unknown>" (off-stack). Fix attributes to the test function.
    assert captured.get("function") == "test_intercept_handler_attributes_to_caller"
    assert captured.get("name") == __name__
    assert captured.get("line") > 0


def test_buggy_frame_walker_attributes_to_callhandlers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the original bug so a future regression reintroduces a detectable failure mode.

    With currentframe() (no .f_back) the while-loop's filename
    check fails on the first iteration, frame is emit's own frame,
    in gitingest's file, not in logging.__file__. So depth stays at
    2 and loguru attributes every intercepted record to stdlib's
    Logger.callHandlers.
    """

    def buggy_emit(_self: logging.Handler, record: logging.LogRecord) -> None:
        try:
            level = logging_config.logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logging_config.logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )

    monkeypatch.setattr(logging_config.InterceptHandler, "emit", buggy_emit)

    captured: dict = {}
    sink_id = logging_config.logger.add(
        lambda msg: captured.update(msg.record),
        level=0,
        format="{message}",
    )
    try:
        logging.getLogger("demo").error("ping")
    finally:
        logging_config.logger.remove(sink_id)

    assert captured.get("function") == "callHandlers"
    assert captured.get("name") == "logging"
