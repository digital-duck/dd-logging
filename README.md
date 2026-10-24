# dd-logging

Shared logging helpers for [Digital Duck](https://github.com/digital-duck) projects.

One consistent pattern for CLI tools and apps: a timestamped log file per run, in
plain text, JSONL, or both. Stdlib only (`logging`, `json`).

Used by **SPL.py**, **graflang**, spl-llm and spl-flow.

## Install

```bash
pip install dd-logging                 # from PyPI
pip install -e /path/to/dd-logging     # local editable install
```

## Usage

```python
from dd_logging import setup_logging, setup_console_logging, get_logger, log_event, disable_logging

# 1. Once per process (CLI entry point or app startup)
log_path = setup_logging(
    "run",
    root_name="my_app",        # top-level logger namespace
    adapter="openrouter",      # appended to the filename (optional)
    model="meta/llama-3",      # appended after the adapter, made filename-safe (optional)
    log_level="info",          # debug | info | warning | error
    log_format="both",         # text | jsonl | both
    console=False,             # also log to stderr (e.g. --verbose)
)
# → logs/run-openrouter-20260215-143022.log      (returned)
#   logs/run-openrouter-20260215-143022.jsonl    (when log_format="both")

# 2. In each module
_log = get_logger("nodes.text2spl", root_name="my_app")
_log.info("translating query  len=%d", len(query))

# 3. Structured events: readable in the .log, queryable fields in the .jsonl
log_event(_log, "node.fire", node="draft", fired=2)
# .log   12:00:01  INFO     my_app.nodes.text2spl  node.fire node=draft fired=2
# .jsonl {"ts": "...", "level": "INFO", "logger": "my_app.nodes.text2spl",
#         "msg": "node.fire node=draft fired=2", "event": "node.fire",
#         "node": "draft", "fired": 2}

# 3b. CLIs that want warnings on screen but a log file only for some commands
setup_console_logging("my_app", "info")     # stderr only; a later setup_logging() replaces it

# 4. Silence everything (e.g. --no-log)
disable_logging("my_app")
```

`setup_logging` returns the primary file: the text file for `text`/`both`, the JSONL
file for `jsonl`.

### JSONL format

One object per line: `ts` (UTC ISO-8601, ms), `level`, `logger`, `msg`, then any
`extra={...}` fields, plus `exc` (formatted traceback) for `log.exception(...)`.
Non-serialisable values are rendered with `str()`. Field names that clash with
`LogRecord` attributes in `log_event` get an `f_` prefix.

```bash
jq -c 'select(.event=="node.fire") | {ts,node}' logs/run-*.jsonl
```

### Environment overrides

Used only when the matching argument is left unset:

| Variable | Meaning |
|----------|---------|
| `DD_LOG_LEVEL` | `debug` / `info` / `warning` / `error` |
| `DD_LOG_DIR` | directory for log files (default `./logs`) |
| `DD_LOG_FORMAT` | `text` / `jsonl` / `both` |

### Per-project facade (recommended)

```python
# myapp/logging_config.py
from pathlib import Path
from dd_logging import ProjectLogging

_pl = ProjectLogging("my_app", log_dir=Path(__file__).resolve().parent.parent / "logs")
get_logger, setup_logging, setup_console_logging, disable_logging, log_event = (
    _pl.get_logger, _pl.setup_logging, _pl.setup_console_logging, _pl.disable_logging, _pl.log_event)
```

Call-sites then write `get_logger("api")` and `setup_logging("run", log_format="both")`.

## Log file naming

```
<log_dir>/<run_name>[-<adapter>][-<model>]-<YYYYMMDD-HHMMSS>.<log|jsonl>
```

## Logger hierarchy

```
my_app                     ← root (file handlers attached here)
├── my_app.api             ← get_logger("api", "my_app")
└── my_app.nodes.text2spl  ← get_logger("nodes.text2spl", "my_app")
```

Child loggers inherit the root's handlers; no per-module setup.

## Design notes

- **`propagate=False`** on the root: no duplicate output when the Python root logger
  already has a handler (Streamlit, pytest, Jupyter).
- **Repeat setup is safe**: handlers from an earlier `setup_logging` call are closed
  and replaced (file and console).
- **Silent until configured**: `get_logger` gives the root a `NullHandler`, so a
  library that logs before `setup_logging` doesn't trip Python's last-resort stderr.
- **No third-party dependencies.**

## Projects using dd-logging

| Project | Root name |
|---------|-----------|
| SPL.py | `spl` |
| graflang | `graflang` |
| spl-flow | `spl_flow` |

## Development

```bash
pip install -e ".[dev]" && pytest
```

## License

MIT
