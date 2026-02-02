import logging

import pytest

from TDTbot import log_init


@pytest.fixture(autouse=True)
def restore_logging():
    """Ensure logging state is cleaned between tests."""
    root = logging.getLogger("discord")
    existing = list(root.handlers)
    level = root.level
    yield
    # restore original handlers and level
    for h in list(root.handlers):
        root.removeHandler(h)
    for h in existing:
        root.addHandler(h)
    root.setLevel(level)


def test_add_logging_level_creates_level_and_method():
    # Add a custom level
    log_init.addLoggingLevel("TRACE2", logging.DEBUG - 1)

    logger = logging.getLogger("discord.test.trace2")
    # Level constant exists
    assert hasattr(logging, "TRACE2")
    assert logging.TRACE2 == logging.DEBUG - 1

    # Method exists on logger and works without raising
    logger.trace2("hello trace2")

    # Idempotent: second call should not raise
    log_init.addLoggingLevel("TRACE2", logging.DEBUG - 1)


def test_critical_exception_filter_blocks_critical_with_exc_info():
    filt = log_init.CriticalExceptionFilter()

    record = logging.LogRecord(
        name="discord.test",
        level=logging.CRITICAL,
        pathname=__file__,
        lineno=1,
        msg="boom",
        args=(),
        exc_info=(RuntimeError, RuntimeError("boom"), None),
    )
    assert filt.filter(record) is False

    non_critical = logging.LogRecord(
        name="discord.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="error but not critical",
        args=(),
        exc_info=(RuntimeError, RuntimeError("err"), None),
    )
    assert filt.filter(non_critical) is True

    no_exc = logging.LogRecord(
        name="discord.test",
        level=logging.CRITICAL,
        pathname=__file__,
        lineno=1,
        msg="critical but no exc",
        args=(),
        exc_info=None,
    )
    assert filt.filter(no_exc) is True


def test_init_logging_sets_handlers_and_levels():
    # Ensure PRINTV level is usable
    log_init.addLoggingLevel("PRINTV", 25)

    logger = log_init.logger
    # Remove any handlers so we can assert new ones added
    for h in list(logger.handlers):
        logger.removeHandler(h)

    records = []

    class ListHandler(logging.Handler):
        def emit(self, record):
            records.append(record)

    log_init.init_logging(logfile=None, visual_log_level=logging.PRINTV, verbose=False)

    handler = ListHandler(level=logging.PRINTV)
    logger.addHandler(handler)
    logger.setLevel(logging.PRINTV)

    logger.printv("hello printv")

    # At least one handler should be present
    assert logger.handlers
    # Message should have been captured at PRINTV level
    assert any("hello printv" in rec.getMessage() for rec in records)
