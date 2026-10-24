"""Core logging helpers shared across Digital Duck projects.

Provides a consistent, timestamped-file logging pattern for CLI tools and
Streamlit apps, in plain-text and/or JSONL form.  Each project supplies its own
*root_name* (the top-level logger namespace) so hierarchies stay isolated:

    spl       → spl / spl.executor        (SPL.py)
    graflang  → graflang / graflang.grafr.runtime
    spl_flow  → spl_flow / spl_flow.nodes.*

Log file naming convention
--------------------------
    <log_dir>/<run_name>[-<adapter>][-<model>]-<YYYYMMDD-HHMMSS>.<ext>
    e.g.  logs/run-openrouter-20260215-143022.log
          logs/run-ollama-gemma3-12b-20260215-143022.log
          logs/run-openrouter-20260215-143022.jsonl

Environment overrides (used only when the matching argument is left unset)
--------------------------------------------------------------------------
    DD_LOG_LEVEL   debug | info | warning | error
    DD_LOG_DIR     directory for log files
    DD_LOG_FORMAT  text | jsonl | both
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Constants ──────────────────────────────────────────────────────────────────

LOG_LEVELS: dict[str, int] = {
    "debug":   logging.DEBUG,
    "info":    logging.INFO,
    "warning": logging.WARNING,
    "error":   logging.ERROR,
}

LOG_FORMATS = ("text", "jsonl", "both")

FORMATTER = logging.Formatter(
    "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

# Attributes every LogRecord has; anything else on a record came in via ``extra=``.
_RESERVED = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime", "taskName"}

# Marks handlers installed by setup_logging so a repeat call can replace them.
_OWNED = "_dd_logging_owned"


# ── Formatters ─────────────────────────────────────────────────────────────────

class JsonlFormatter(logging.Formatter):
    """One JSON object per line: ``ts`` (UTC ISO-8601), ``level``, ``logger``, ``msg``,
    any ``extra=`` fields, and ``exc`` when an exception is attached.

    Values that are not JSON-serialisable are rendered with ``str()``.
    """

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc)
                          .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str, ensure_ascii=False)


# ── Public API ─────────────────────────────────────────────────────────────────

def setup_logging(
    run_name: str,
    *,
    root_name: str,
    adapter: str = "",
    model: str = "",
    log_level: str | None = None,
    log_dir: Path | str | None = None,
    console: bool = False,
    log_ext: str | None = None,
    log_format: str | None = None,
) -> Path:
    """Attach timestamped file handler(s) to the *root_name* logger.

    Safe to call multiple times in one process: handlers installed by an earlier
    call are closed and replaced.

    Parameters
    ----------
    run_name   : short label for the filename, e.g. ``"run"``, ``"benchmark"``
    root_name  : root logger namespace, e.g. ``"spl"`` or ``"graflang"``
    adapter    : LLM adapter name appended to the filename (omitted if empty)
    model      : model id appended after the adapter (omitted if empty); characters other
                 than letters, digits, ``.``, ``_`` and ``-`` become ``-`` (``gemma3:12b`` -> ``gemma3-12b``)
    log_level  : ``"debug"`` | ``"info"`` | ``"warning"`` | ``"error"``
                 (default: ``$DD_LOG_LEVEL`` or ``"info"``)
    log_dir    : directory for log files (default: ``$DD_LOG_DIR`` or ``./logs``)
    console    : also attach a text StreamHandler to stderr (CLI --verbose mode)
    log_ext    : extension of the primary file (default ``.log``, or ``.jsonl``
                 when *log_format* is ``"jsonl"``)
    log_format : ``"text"`` (default, or ``$DD_LOG_FORMAT``), ``"jsonl"``, or
                 ``"both"`` (a ``.log`` and a ``.jsonl`` side by side)

    Returns
    -------
    Path  absolute path of the primary log file (the text file for ``"text"``
          and ``"both"``, the JSONL file for ``"jsonl"``)
    """
    fmt = (log_format or os.environ.get("DD_LOG_FORMAT") or "text").lower()
    if fmt not in LOG_FORMATS:
        raise ValueError(f"log_format must be one of {LOG_FORMATS}, got {fmt!r}")
    level_name = (log_level or os.environ.get("DD_LOG_LEVEL") or "info").lower()
    level = LOG_LEVELS.get(level_name, logging.INFO)

    target_dir = Path(log_dir or os.environ.get("DD_LOG_DIR") or Path.cwd() / "logs")
    target_dir.mkdir(parents=True, exist_ok=True)

    dt_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = f"-{adapter}" if adapter else ""
    if model:
        suffix += "-" + re.sub(r"[^A-Za-z0-9._-]+", "-", model).strip("-")
    stem = f"{run_name}{suffix}-{dt_str}"

    def _ext(default: str) -> str:
        ext = log_ext if (log_ext and fmt != "both") else default
        return ext if ext.startswith(".") else f".{ext}"

    files: list[tuple[Path, logging.Formatter]] = []
    if fmt in ("text", "both"):
        files.append((target_dir / f"{stem}{_ext('.log')}", FORMATTER))
    if fmt in ("jsonl", "both"):
        # "both" always writes .jsonl so it cannot collide with the text file
        files.append((target_dir / f"{stem}{'.jsonl' if fmt == 'both' else _ext('.jsonl')}",
                      JsonlFormatter()))

    root = logging.getLogger(root_name)
    root.setLevel(logging.DEBUG)   # capture everything; handlers filter
    _drop_owned(root)

    for path, formatter in files:
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(formatter)
        setattr(fh, _OWNED, True)
        root.addHandler(fh)

    if console:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(FORMATTER)
        setattr(ch, _OWNED, True)
        root.addHandler(ch)

    # Prevent propagation to the Python root logger — avoids duplicate output
    # in environments that configure their own root handler (e.g. Streamlit).
    root.propagate = False

    return files[0][0].resolve()


def setup_console_logging(root_name: str, log_level: str | None = None) -> None:
    """Attach only a text StreamHandler (stderr) to *root_name*: for CLIs that want warnings on screen
    but no log file until a command asks for one.  A later ``setup_logging`` replaces this handler
    (pass ``console=True`` there to keep console output)."""
    level = LOG_LEVELS.get((log_level or os.environ.get("DD_LOG_LEVEL") or "info").lower(), logging.INFO)
    root = logging.getLogger(root_name)
    root.setLevel(logging.DEBUG)
    _drop_owned(root)
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(FORMATTER)
    setattr(ch, _OWNED, True)
    root.addHandler(ch)
    root.propagate = False


def get_logger(name: str, root_name: str) -> logging.Logger:
    """Return a child logger under *root_name*.

    The root gets a ``NullHandler`` if it has none, so a library that logs before
    (or without) ``setup_logging`` stays silent instead of hitting Python's
    last-resort stderr handler.
    """
    root = logging.getLogger(root_name)
    if not root.handlers:
        root.addHandler(logging.NullHandler())
    return logging.getLogger(f"{root_name}.{name}") if name else root


def log_event(logger: logging.Logger, event: str, *, level: int = logging.INFO,
              **fields: Any) -> None:
    """Log a structured event: message ``"<event> k=v ..."`` plus *fields* as JSONL keys.

    ``event`` is stored under the ``event`` key.  Field names that collide with
    ``LogRecord`` attributes (``name``, ``msg``, ...) are prefixed with ``f_``.
    """
    if not logger.isEnabledFor(level):
        return
    extra = {("f_" + k if k in _RESERVED or k == "event" else k): v
             for k, v in fields.items()}
    extra["event"] = event
    text = " ".join([event] + [f"{k}={_render(v)}" for k, v in fields.items()])
    logger.log(level, text, extra=extra, stacklevel=2)


def _render(value: Any) -> str:
    """A field value for the one-line message: strings with spaces/newlines/quotes are JSON-quoted."""
    if isinstance(value, str) and (not value or any(c.isspace() or c in '="' for c in value)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def disable_logging(root_name: str) -> None:
    """Close and remove all handlers from *root_name* logger (no-op log mode)."""
    root = logging.getLogger(root_name)
    for h in list(root.handlers):
        root.removeHandler(h)
        h.close()
    root.propagate = False


def _drop_owned(root: logging.Logger) -> None:
    for h in list(root.handlers):
        if getattr(h, _OWNED, False) or type(h) is logging.FileHandler:
            root.removeHandler(h)
            h.close()


class ProjectLogging:
    """Per-project facade so call-sites never pass ``root_name`` or ``log_dir``.

        # myapp/logging_config.py
        from dd_logging import ProjectLogging
        _pl = ProjectLogging("myapp", log_dir=Path(__file__).parent.parent / "logs")
        get_logger, setup_logging, disable_logging, log_event = (
            _pl.get_logger, _pl.setup_logging, _pl.disable_logging, _pl.log_event)
    """

    def __init__(self, root_name: str, *, log_dir: Path | str | None = None):
        self.root_name = root_name
        self.log_dir = log_dir

    def get_logger(self, name: str = "") -> logging.Logger:
        return get_logger(name, self.root_name)

    def setup_logging(self, run_name: str, **kw: Any) -> Path:
        if self.log_dir is not None:
            kw.setdefault("log_dir", self.log_dir)
        return setup_logging(run_name, root_name=self.root_name, **kw)

    def setup_console_logging(self, log_level: str | None = None) -> None:
        setup_console_logging(self.root_name, log_level)

    def disable_logging(self) -> None:
        disable_logging(self.root_name)

    log_event = staticmethod(log_event)
