# Changelog

## 0.2.0

### Added
- `ProjectLogging`: one object per project that owns a root logger (`get_logger`, `setup_logging`, `log_event`, `disable_logging`).
- JSONL and "both" formats (`log_format`, `$DD_LOG_FORMAT`): a `.log` for people and a `.jsonl` for tools, side by side.
- `log_event(logger, "noun.verb", **fields)`: fields become JSONL keys.
- `model` in the file name: `<run>[-<adapter>][-<model>]-<timestamp>`, with the model made filename-safe.

### Changed
- File naming is documented in the README; `$DD_LOG_LEVEL`, `$DD_LOG_DIR` and `$DD_LOG_FORMAT` apply when the argument is left unset.
