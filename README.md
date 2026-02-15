# dd-logging

Shared logging helpers for [Digital Duck](https://github.com/digital-duck) projects.

Provides a consistent, timestamped-file logging pattern for CLI tools and Streamlit apps.
Used by **spl-llm** and **spl-flow**; designed to be reused by any project in the ecosystem.

## Install

```bash
# from PyPI (once published)
pip install dd-logging

# local editable install (for development)
pip install -e /path/to/dd-logging
```

## Usage

```python
from dd_logging import setup_logging, get_logger, disable_logging

# 1. Call once per process (CLI entry point or app startup)
log_path = setup_logging(
    "run",
    root_name="my_app",       # top-level logger namespace
    adapter="openrouter",     # appended to filename (optional)
    log_level="info",         # debug | info | warning | error
)
# → logs/run-openrouter-20260215-143022.log

# 2. In each module
_log = get_logger("nodes.text2spl", root_name="my_app")
_log.info("translating query  len=%d", len(query))

# 3. Silence all logging (e.g. --no-log CLI flag)
disable_logging("my_app")
```

### Thin wrapper pattern (recommended)

Each project wraps `dd_logging` so call-sites never pass `root_name`:

```python
# myapp/logging_config.py
from pathlib import Path
from dd_logging import setup_logging as _setup, get_logger as _get, disable_logging as _disable

_ROOT   = "my_app"
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

def get_logger(name: str):
    return _get(name, _ROOT)

def setup_logging(run_name: str, **kw):
    kw.setdefault("log_dir", LOG_DIR)
    return _setup(run_name, root_name=_ROOT, **kw)

def disable_logging():
    return _disable(_ROOT)
```

## Log file naming

```
<log_dir>/<run_name>[-<adapter>]-<YYYYMMDD-HHMMSS>.log

logs/run-openrouter-20260215-143022.log
logs/benchmark-claude_cli-20260215-144500.log
logs/generate-20260215-145001.log
```

## Logger hierarchy

```
my_app                     ← root (FileHandler attached here)
├── my_app.api             ← get_logger("api", "my_app")
├── my_app.nodes.text2spl  ← get_logger("nodes.text2spl", "my_app")
└── my_app.flows           ← get_logger("flows", "my_app")
```

All child loggers inherit the root's handler — no per-module handler setup needed.

## Design notes

- **`propagate=False`** — prevents duplicate output when a root Python logger
  handler is already configured (e.g. Streamlit, pytest, Jupyter).
- **Stale-handler removal** — calling `setup_logging()` multiple times in one
  process (e.g. test suites) is safe; old `FileHandler`s are replaced.
- **No third-party dependencies** — stdlib `logging` only.

## Projects using dd-logging

| Project | Root name | Log dir |
|---------|-----------|---------|
| [spl-llm](https://github.com/digital-duck/SPL) | `spl` | `SPL/logs/` |
| [spl-flow](https://github.com/digital-duck/SPL-Flow) | `spl_flow` | `SPL-Flow/logs/` |

## License

MIT
