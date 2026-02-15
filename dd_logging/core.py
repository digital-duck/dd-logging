"""Core logging helpers shared across Digital Duck projects.

Provides a consistent, timestamped-file logging pattern for CLI tools and
Streamlit apps.  Each project supplies its own *root_name* (the top-level
logger namespace) so hierarchies stay isolated:

    spl       → spl / spl.executor   (spl-llm package)
    spl_flow  → spl_flow / spl_flow.nodes.*  (spl-flow package)

Log file naming convention
--------------------------
    <log_dir>/<run_name>[-<adapter>]-<YYYYMMDD-HHMMSS>.log
    e.g.  logs/run-openrouter-20260215-143022.log
          logs/benchmark-claude_cli-20260215-144500.log
          logs/generate-20260215-145001.log
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

LOG_LEVELS: dict[str, int] = {
    "debug":   logging.DEBUG,
    "info":    logging.INFO,
    "warning": logging.WARNING,
    "error":   logging.ERROR,
}

FORMATTER = logging.Formatter(
    "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

# ── Public API ─────────────────────────────────────────────────────────────────

def setup_logging(
    run_name: str,
    *,
    root_name: str,
    adapter: str = "",
    log_level: str = "info",
    log_dir: Path | str | None = None,
    console: bool = False,
) -> Path:
    """Attach a timestamped FileHandler to *root_name* logger.

    Safe to call multiple times in one process — stale FileHandlers from
    a previous call are removed before the new one is attached.

    Parameters
    ----------
    run_name  : short label for the filename, e.g. ``"run"``, ``"benchmark"``
    root_name : root logger namespace, e.g. ``"spl"`` or ``"spl_flow"``
    adapter   : LLM adapter name appended to the filename (omitted if empty)
    log_level : ``"debug"`` | ``"info"`` | ``"warning"`` | ``"error"``
    log_dir   : directory for log files; defaults to ``./logs`` relative to CWD
    console   : also attach a StreamHandler (useful in CLI --verbose mode)

    Returns
    -------
    Path  absolute path of the log file created
    """
    target_dir = Path(log_dir) if log_dir else Path.cwd() / "logs"
    target_dir.mkdir(parents=True, exist_ok=True)

    dt_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = f"-{adapter}" if adapter else ""
    log_path = target_dir / f"{run_name}{suffix}-{dt_str}.log"

    level = LOG_LEVELS.get(log_level.lower(), logging.INFO)

    root = logging.getLogger(root_name)
    root.setLevel(logging.DEBUG)   # capture everything; handlers filter

    # Remove stale FileHandlers from a previous setup_logging() call
    root.handlers = [h for h in root.handlers if not isinstance(h, logging.FileHandler)]

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(FORMATTER)
    root.addHandler(fh)

    if console:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(FORMATTER)
        root.addHandler(ch)

    # Prevent propagation to the Python root logger — avoids duplicate output
    # in environments that configure their own root handler (e.g. Streamlit).
    root.propagate = False

    return log_path


def get_logger(name: str, root_name: str) -> logging.Logger:
    """Return a child logger under *root_name*.

    Parameters
    ----------
    name      : dotted sub-path, e.g. ``"nodes.text2spl"`` or ``"executor"``
    root_name : root logger namespace, e.g. ``"spl"`` or ``"spl_flow"``

    Returns
    -------
    logging.Logger  named  ``<root_name>.<name>``
    """
    return logging.getLogger(f"{root_name}.{name}")


def disable_logging(root_name: str) -> None:
    """Remove all handlers from *root_name* logger (no-op log mode)."""
    root = logging.getLogger(root_name)
    root.handlers.clear()
    root.propagate = False
