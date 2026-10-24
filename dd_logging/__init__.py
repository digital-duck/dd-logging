"""dd-logging — shared logging helpers for Digital Duck projects."""
from dd_logging.core import (
    FORMATTER,
    LOG_FORMATS,
    LOG_LEVELS,
    JsonlFormatter,
    ProjectLogging,
    disable_logging,
    get_logger,
    log_event,
    setup_console_logging,
    setup_logging,
)

__version__ = "0.2.0"

__all__ = [
    "setup_logging",
    "setup_console_logging",
    "get_logger",
    "log_event",
    "disable_logging",
    "ProjectLogging",
    "JsonlFormatter",
    "LOG_LEVELS",
    "LOG_FORMATS",
    "FORMATTER",
]
