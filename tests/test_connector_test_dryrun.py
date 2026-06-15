import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from dojo import db


from helpers import run_cli


def script(tmp_path, body):
    path = tmp_path / "connector.py"
    path.write_text(body)
    return [sys.executable, str(path)]


def setup_connector(tmp_path, *, name="hermes", body="print('{}')", default=True):
    argv = script(tmp_path, body)
    db_path = tmp_path / "dojo.sqlite3"
    db.init_db(db_path)
    with db.connect(db_path) as session:
        db.save_ai_connector(
            session,
            name=name,
            argv=argv,
            is_default=default,
            replace=True
        )
    return db_path


def test_connector_test_success(tmp_path):
    # Set up a connector that prints a valid JSON structure (or text) and exits with 0
    setup_connector(tmp_path, name="good_conn", body="print('{\"success\": true}')")

    # Run dojo connect ai test good_conn
    result = run_cli(tmp_path, "--json", "connect", "ai", "test", "good_conn")
    res = json.loads(result.stdout)
    assert res["connector_name"] == "good_conn"
    assert res["status"] == "ok"
    assert res["exit_code"] == 0
    assert "{\"success\": true}" in res["stdout"]

    # Verify db was updated
    db_path = tmp_path / "dojo.sqlite3"
    with db.connect(db_path) as session:
        connector = db.get_ai_connector(session, "good_conn")
        assert connector["last_test_status"] == "ok"
        assert "Success" in connector["last_test_summary"]
        assert connector["last_test_at"] is not None


def test_connector_test_failure(tmp_path):
    # Set up a connector that exits with non-zero
    setup_connector(tmp_path, name="bad_conn", body="import sys; print('error output', file=sys.stderr); sys.exit(5)")

    # Run dojo connect ai test bad_conn (assert non-zero exit code)
    result = run_cli(tmp_path, "--json", "connect", "ai", "test", "bad_conn", check=False)
    assert result.returncode != 0

    res = json.loads(result.stdout)
    assert res["connector_name"] == "bad_conn"
    assert res["status"] == "failed"
    assert res["exit_code"] == 5
    assert "error output" in res["stderr"]

    # Verify db was updated
    db_path = tmp_path / "dojo.sqlite3"
    with db.connect(db_path) as session:
        connector = db.get_ai_connector(session, "bad_conn")
        assert connector["last_test_status"] == "failed"
        assert "Failed" in connector["last_test_summary"]


def test_connector_test_default_fallback(tmp_path):
    setup_connector(tmp_path, name="default_conn", body="print('ok')")

    # Run test without specifying name
    result = run_cli(tmp_path, "--json", "connect", "ai", "test")
    res = json.loads(result.stdout)
    assert res["connector_name"] == "default_conn"
    assert res["status"] == "ok"


def test_request_dry_run_exercise_generate(tmp_path):
    # Dry run does not require database/connector presence for exercise.generate
    result = run_cli(tmp_path, "--json", "connect", "ai", "request", "exercise.generate", "--dry-run")
    res = json.loads(result.stdout)

    assert "task_request" in res
    assert "rendered_prompt" in res
    assert res["task_request"]["task"] == "exercise.generate"
    assert "Dry Run Source" in res["task_request"]["source"]["title"]
    assert "exercise.generate" in res["rendered_prompt"]


def test_request_dry_run_generic(tmp_path):
    result = run_cli(tmp_path, "--json", "connect", "ai", "request", "custom.task", "--dry-run")
    res = json.loads(result.stdout)

    assert res["task_request"]["task"] == "custom.task"
    assert "custom.task" in res["rendered_prompt"]


def test_request_invocation(tmp_path):
    # Setup default connector
    setup_connector(tmp_path, name="exec_conn", body="print('{\"echo\": \"done\"}')")

    # Run request without --dry-run
    result = run_cli(tmp_path, "--json", "connect", "ai", "request", "exercise.generate")
    res = json.loads(result.stdout)
    assert res["status"] == "ok"
    assert "echo" in res["parsed_stdout"]
