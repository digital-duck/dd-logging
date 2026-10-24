import json
import logging

import pytest

from dd_logging import (JsonlFormatter, ProjectLogging, disable_logging, get_logger,
                        log_event, setup_console_logging, setup_logging)


@pytest.fixture
def root():
    name = "ddtest"
    yield name
    disable_logging(name)


def _flush(name):
    for h in logging.getLogger(name).handlers:
        h.flush()


def test_text_file_naming_and_content(tmp_path, root):
    path = setup_logging("run", root_name=root, adapter="mock", log_dir=tmp_path)
    assert path.parent == tmp_path.resolve()
    assert path.name.startswith("run-mock-") and path.suffix == ".log"
    get_logger("mod", root).info("hello %s", "world")
    _flush(root)
    text = path.read_text()
    assert "INFO" in text and "ddtest.mod" in text and "hello world" in text


def test_model_id_is_added_to_the_filename_and_made_filename_safe(tmp_path, root):
    path = setup_logging("run", root_name=root, adapter="ollama", model="gemma3:12b", log_dir=tmp_path)
    assert path.name.startswith("run-ollama-gemma3-12b-")
    path = setup_logging("run", root_name=root, adapter="openrouter", model="meta/llama-3", log_dir=tmp_path)
    assert path.name.startswith("run-openrouter-meta-llama-3-")
    path = setup_logging("run", root_name=root, model="m1", log_dir=tmp_path)
    assert path.name.startswith("run-m1-")
    path = setup_logging("run", root_name=root, adapter="mock", model="", log_dir=tmp_path)
    assert path.name.startswith("run-mock-2")


def test_level_filters(tmp_path, root):
    path = setup_logging("run", root_name=root, log_dir=tmp_path, log_level="warning")
    log = get_logger("m", root)
    log.info("quiet")
    log.warning("loud")
    _flush(root)
    text = path.read_text()
    assert "loud" in text and "quiet" not in text


def test_jsonl_records(tmp_path, root):
    path = setup_logging("run", root_name=root, log_dir=tmp_path, log_format="jsonl")
    assert path.suffix == ".jsonl"
    log = get_logger("m", root)
    log.info("plain")
    log.info("with extra", extra={"node": "n1", "obj": object()})
    try:
        1 / 0
    except ZeroDivisionError:
        log.exception("boom")
    _flush(root)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["msg"] == "plain" and rows[0]["logger"] == "ddtest.m"
    assert rows[0]["level"] == "INFO" and rows[0]["ts"].endswith("+00:00")
    assert rows[1]["node"] == "n1" and isinstance(rows[1]["obj"], str)
    assert "ZeroDivisionError" in rows[2]["exc"]


def test_both_writes_two_files(tmp_path, root):
    path = setup_logging("run", root_name=root, log_dir=tmp_path, log_format="both")
    assert path.suffix == ".log"
    get_logger("m", root).info("x")
    _flush(root)
    files = sorted(p.suffix for p in tmp_path.iterdir())
    assert files == [".jsonl", ".log"]


def test_log_event_fields(tmp_path, root):
    path = setup_logging("run", root_name=root, log_dir=tmp_path, log_format="jsonl")
    log_event(get_logger("m", root), "node.fire", node="gen", name="clash", n=2)
    _flush(root)
    row = json.loads(path.read_text())
    assert row["event"] == "node.fire" and row["node"] == "gen" and row["n"] == 2
    assert row["f_name"] == "clash" and row["logger"] == "ddtest.m"
    assert row["msg"].startswith("node.fire node=gen")


def test_log_event_skips_disabled_level(tmp_path, root):
    path = setup_logging("run", root_name=root, log_dir=tmp_path,
                         log_level="warning", log_format="jsonl")
    log_event(get_logger("m", root), "dbg", level=logging.DEBUG)
    _flush(root)
    assert path.read_text() == ""


def test_repeat_setup_replaces_handlers(tmp_path, root):
    setup_logging("a", root_name=root, log_dir=tmp_path, console=True)
    setup_logging("b", root_name=root, log_dir=tmp_path, console=True)
    # (pytest 9 also attaches its own capture handlers to non-propagating loggers)
    owned = [h for h in logging.getLogger(root).handlers
             if getattr(h, "_dd_logging_owned", False)]
    assert len(owned) == 2    # one file + one console, not four


def test_no_propagation(tmp_path, root):
    setup_logging("run", root_name=root, log_dir=tmp_path)
    assert logging.getLogger(root).propagate is False


def test_disable_closes_handlers(tmp_path, root):
    setup_logging("run", root_name=root, log_dir=tmp_path)
    fh = next(h for h in logging.getLogger(root).handlers
              if isinstance(h, logging.FileHandler))
    disable_logging(root)
    assert logging.getLogger(root).handlers == [] and fh.stream is None


def test_env_overrides(tmp_path, root, monkeypatch):
    monkeypatch.setenv("DD_LOG_DIR", str(tmp_path / "envlogs"))
    monkeypatch.setenv("DD_LOG_FORMAT", "jsonl")
    monkeypatch.setenv("DD_LOG_LEVEL", "debug")
    path = setup_logging("run", root_name=root)
    assert path.parent.name == "envlogs" and path.suffix == ".jsonl"
    get_logger("m", root).debug("d")
    _flush(root)
    assert json.loads(path.read_text())["level"] == "DEBUG"


def test_bad_format_rejected(tmp_path, root):
    with pytest.raises(ValueError):
        setup_logging("run", root_name=root, log_dir=tmp_path, log_format="xml")


def test_get_logger_unconfigured_is_silent(capsys):
    get_logger("x", "ddtest_unconfigured").warning("nobody listening")
    assert capsys.readouterr().err == ""
    logging.getLogger("ddtest_unconfigured").handlers.clear()


def test_project_logging_facade(tmp_path, root):
    pl = ProjectLogging(root, log_dir=tmp_path)
    path = pl.setup_logging("run", log_format="jsonl")
    pl.log_event(pl.get_logger("m"), "ev", k=1)
    _flush(root)
    row = json.loads(path.read_text())
    assert path.parent == tmp_path.resolve() and row["event"] == "ev" and row["k"] == 1
    assert row["logger"] == "ddtest.m"


def test_jsonl_formatter_standalone():
    rec = logging.LogRecord("n", logging.INFO, "f", 1, "m %d", (3,), None)
    assert json.loads(JsonlFormatter().format(rec))["msg"] == "m 3"


def test_log_event_quotes_multiline_strings(tmp_path, root):
    path = setup_logging("run", root_name=root, log_dir=tmp_path)
    log_event(get_logger("m", root), "llm.text", prompt="line1\nline2", ok="plain")
    _flush(root)
    lines = path.read_text().splitlines()
    assert len(lines) == 1 and 'prompt="line1\\nline2" ok=plain' in lines[0]


def test_console_only_then_file_replaces_it(tmp_path, root, capsys):
    setup_console_logging(root, "warning")
    log = get_logger("m", root)
    log.info("hidden")
    log.warning("shown")
    err = capsys.readouterr().err
    assert "shown" in err and "hidden" not in err
    assert list(tmp_path.iterdir()) == []
    setup_logging("run", root_name=root, log_dir=tmp_path)       # no console=True -> stderr handler dropped
    log.warning("file only")
    assert "file only" not in capsys.readouterr().err
