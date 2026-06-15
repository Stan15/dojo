import json
import sys

from dojo import db
from dojo.connectors import invoke_command_connector


def add_connector(tmp_path, *, name="fake", argv, input_mode="stdin-prompt", timeout=120, default=True):
    db_path = tmp_path / "dojo.sqlite3"
    db.init_db(db_path)
    with db.connect(db_path) as conn:
        db.save_ai_connector(conn, name=name, argv=argv, input_mode=input_mode, timeout_seconds=timeout, is_default=default)
    return db_path


def script(tmp_path, body):
    path = tmp_path / "connector.py"
    path.write_text(body)
    return [sys.executable, str(path)]


def test_stdin_prompt_reaches_subprocess_and_json_stdout_parses(tmp_path):
    argv = script(tmp_path, "import json, sys; print(json.dumps({'echo': sys.stdin.read()}))")
    db_path = add_connector(tmp_path, argv=argv)
    result = invoke_command_connector(db_path, {"task": "echo", "payload": {"text": "hello"}})
    assert result.status == "ok"
    assert result.parse_status == "json"
    assert "hello" in result.parsed_stdout["echo"]
    assert result.raw_stdout


def test_stdin_json_and_request_file_modes(tmp_path):
    argv = script(tmp_path, "import json, sys; print(json.dumps(json.loads(sys.stdin.read())))")
    db_path = add_connector(tmp_path, argv=argv, input_mode="stdin-json")
    result = invoke_command_connector(db_path, {"task": "exercise.generate"})
    assert result.status == "ok"
    assert result.parsed_stdout["task"] == "exercise.generate"

    marker = tmp_path / "marker.txt"
    argv = script(tmp_path, f"import json, os, pathlib; p=pathlib.Path(os.environ['DOJO_TASK_REQUEST_FILE']); pathlib.Path({str(marker)!r}).write_text(p.read_text()); print('{{}}')")
    db_path = add_connector(tmp_path, name="filemode", argv=argv, input_mode="request-json-file")
    result = invoke_command_connector(db_path, {"task": "file-mode"}, connector_name="filemode")
    assert result.status == "ok"
    assert json.loads(marker.read_text())["task"] == "file-mode"


def test_text_stdout_nonzero_timeout_and_missing_default_are_structured(tmp_path):
    argv = script(tmp_path, "print('plain text')")
    db_path = add_connector(tmp_path, argv=argv)
    text = invoke_command_connector(db_path, {"task": "x"})
    assert text.status == "ok"
    assert text.parse_status == "text"
    assert text.raw_stdout.strip() == "plain text"
    assert "not JSON" in text.parse_warning

    argv = script(tmp_path, "import sys; print('bad', file=sys.stderr); sys.exit(7)")
    db_path = add_connector(tmp_path, name="bad", argv=argv)
    failed = invoke_command_connector(db_path, {"task": "x"})
    assert failed.status == "failed"
    assert failed.exit_code == 7
    assert "bad" in failed.stderr_tail

    argv = script(tmp_path, "import time; time.sleep(5)")
    db_path = add_connector(tmp_path, name="slow", argv=argv, timeout=1)
    timed = invoke_command_connector(db_path, {"task": "x"})
    assert timed.status == "timeout"
    assert "timed out" in timed.error

    db_path = add_connector(tmp_path / "missing", argv=[sys.executable, "-c", "print('{}')"], default=False)
    missing = invoke_command_connector(db_path, {"task": "x"})
    assert missing.status == "failed"
    assert "no default AI connector" in missing.error
