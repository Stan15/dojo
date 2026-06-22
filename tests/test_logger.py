import json
from unittest.mock import patch
from dojo import db
from dojo.api import DojoAPI
from dojo.logger import get_logger
from helpers import run_cli


def test_logger_setup(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    log = get_logger(db_path, "test_logger")
    
    # Assert log file is created in same directory
    log_file = tmp_path / "dojo.log"
    assert log_file.exists()
    
    # Write a log message
    log.info("Hello logger world!")
    
    # Check log contents
    content = log_file.read_text(encoding="utf-8")
    assert "Hello logger world!" in content
    assert "[INFO]" in content
    assert "test_logger" in content


def test_cli_debug_run(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    db.init_db(db_path)
    
    # 1. Insert mock generation run record
    request_data = {"task": "exercise.generate", "prompt": "Gen prompt"}
    diagnostics_data = {"diagnostics": ["Mock schema mismatch"], "stderr": "Traceback..."}
    
    with db.connect(db_path) as session:
        run = db.GenerationRun(
            task="exercise.generate",
            request_json=json.dumps(request_data),
            raw_output="Raw LLM stdout",
            status="failed",
            diagnostics_json=json.dumps(diagnostics_data)
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id
        
    # 2. Run CLI command under human-friendly text mode (mock _use_json to return False)
    with patch("dojo.cli._use_json", return_value=False):
        res_text = run_cli(tmp_path, "admin", "debug-run", str(run_id))
    
    assert f"Generation Run Debugger - Run ID: {run_id}" in res_text.stdout
    assert "Task: exercise.generate" in res_text.stdout
    assert "Status: failed" in res_text.stdout
    assert "Gen prompt" in res_text.stdout
    assert "Raw LLM stdout" in res_text.stdout
    assert "Mock schema mismatch" in res_text.stdout
    assert "Traceback..." in res_text.stdout
    
    # 3. Run CLI command under JSON mode
    res_json = run_cli(tmp_path, "--json", "admin", "debug-run", str(run_id))
    data = json.loads(res_json.stdout)
    assert data["ok"] is True
    assert data["type"] == "generation_run"
    assert data["data"]["id"] == run_id
    assert data["data"]["status"] == "failed"
    assert data["data"]["request"]["prompt"] == "Gen prompt"
    
    # 4. Request unknown run id
    res_err = run_cli(tmp_path, "admin", "debug-run", "999", check=False)
    assert res_err.returncode != 0
    assert "generation run 999 not found" in res_err.stderr
