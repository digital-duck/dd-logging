"""dd-logging — shared logging helpers for Digital Duck projects."""
from dd_logging.core import (
    FORMATTER,
    LOG_LEVELS,
    disable_logging,
    get_logger,
    setup_logging,
)

__version__ = "0.1.0"

__all__ = [
    "setup_logging",
    "get_logger",
    "disable_logging",
    "LOG_LEVELS",
    "FORMATTER",
]
