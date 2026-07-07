import json
import os
import subprocess
import sys
from pathlib import Path
from dojo import db


from helpers import run_cli


def script(tmp_path, body):
    path = tmp_path / "connector.py"
    path.write_text(body)
    return [sys.executable, str(path)]


def add_connector(tmp_path, *, name="fake", argv, input_mode="stdin-prompt", default=True):
    db_path = tmp_path / "dojo.sqlite3"
    db.init_db(db_path)
    with db.connect(db_path) as session:
        db.save_ai_connector(
            session,
            name=name,
            argv=argv,
            input_mode=input_mode,
            is_default=default,
            replace=True,
        )
    return db_path


def test_dojo_add_source_only(tmp_path):
    # Verify we can add a text-only source without generation
    out = run_cli(
        tmp_path,
        "add",
        "--text", "Calculus notes here.",
        "--title", "Calc Notes",
        "--topic", "math.calculus",
        "--mission", "Master the basics",
    ).stdout
    res = json.loads(out)
    assert res["source_id"].startswith("src_")
    assert res["title"] == "Calc Notes"
    assert res["kind"] == "text"
    assert res["candidates_count"] == 0

    # Verify database state
    db_path = tmp_path / "dojo.sqlite3"
    with db.connect(db_path) as session:
        src = db.get_source(session, res["source_id"])
        assert src is not None
        assert src["content"] == "Calculus notes here."
        assert src["mission"] == "Master the basics"


def test_dojo_add_file_source_only(tmp_path):
    # Create a dummy note file
    note_file = tmp_path / "notes.txt"
    note_file.write_text("Linear algebra vectors notes.")

    out = run_cli(
        tmp_path,
        "add",
        str(note_file),
        "--topic", "math.la",
        "--mission", "Understand vectors",
    ).stdout
    res = json.loads(out)
    assert res["source_id"].startswith("src_")
    assert res["title"] == "notes.txt"
    assert res["kind"] == "file"
    assert res["candidates_count"] == 0

    # Verify database state
    db_path = tmp_path / "dojo.sqlite3"
    with db.connect(db_path) as session:
        src = db.get_source(session, res["source_id"])
        assert src is not None
        assert src["content"] == "Linear algebra vectors notes."
        assert src["mission"] == "Understand vectors"


def test_dojo_add_generate_tracer_bullet(tmp_path):
    # 1. Define a mock connector that returns a valid exercise candidate JSON
    candidates_data = {
        "candidates": [
            {
                "prompt": "Compute the derivative of x^2.",
                "answer": "2x",
                "topic_path": "math.calculus.derivatives",
                "source_refs": {
                    "start_line": 1,
                    "end_line": 2,
                    "anchor_text": "Derivative of power"
                },
                "difficulty": "easy"
            }
        ]
    }
    connector_script = script(
        tmp_path,
        f"import json; print(json.dumps({candidates_data!r}))"
    )

    # 2. Persist this connector as default in the test DB
    add_connector(tmp_path, argv=connector_script)

    # 3. Add a source with --generate
    out = run_cli(
        tmp_path,
        "add",
        "--text", "Power rule notes.",
        "--title", "Power Rule",
        "--topic", "math.calculus",
        "--mission", "Focus on power rule",
        "--generate",
    ).stdout
    res = json.loads(out)
    assert res["source_id"].startswith("src_")
    assert res["candidates_count"] == 1
    assert "generation_run_id" in res

    # 4. Verify candidates and runs are persisted in DB
    db_path = tmp_path / "dojo.sqlite3"
    with db.connect(db_path) as session:
        candidates = db.list_candidates(session, res["source_id"])
        assert len(candidates) == 1
        cand = candidates[0]
        assert cand["prompt"] == "Compute the derivative of x^2."
        assert cand["answer"] == "2x"
        assert cand["topic_path"] == "math.calculus.derivatives"
        assert cand["source_refs"] == [{
            "start_line": 1,
            "end_line": 2,
            "anchor_text": "Derivative of power"
        }]
        assert cand["generation_run_id"] == res["generation_run_id"]
