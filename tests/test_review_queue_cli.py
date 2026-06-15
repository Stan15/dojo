import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from dojo import db


from helpers import run_cli


def setup_test_data(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    db.init_db(db_path)
    with db.connect(db_path) as session:
        # Create a source
        db.save_source(
            session,
            id="src_test",
            title="Physics Notes",
            content="Force equals mass times acceleration.",
            kind="text",
            mission="Understand Newtonian mechanics",
        )
        
        # Create candidates
        db.save_candidate(
            session,
            id="cand_physics_1",
            source_id="src_test",
            prompt="What is F=ma?",
            answer="Force equals mass times acceleration",
            rubric={"grading": "exact match"},
            topic_path="physics.newton.fma",
            source_refs={"start_line": 1, "end_line": 1, "anchor_text": "F=ma"},
            difficulty="easy",
        )
        db.save_candidate(
            session,
            id="cand_physics_2",
            source_id="src_test",
            prompt="What is gravity acceleration on Earth?",
            answer="9.8 m/s^2",
            rubric={"grading": "approximate"},
            topic_path="physics.newton.gravity",
            source_refs={"start_line": 1, "end_line": 1, "anchor_text": "gravity"},
            difficulty="medium",
        )
    return db_path


def test_source_list_text_and_json(tmp_path):
    setup_test_data(tmp_path)
    
    # Test JSON output
    result_json = run_cli(tmp_path, "--json", "source", "list")
    data = json.loads(result_json.stdout)
    assert len(data) == 1
    assert data[0]["id"] == "src_test"
    assert data[0]["title"] == "Physics Notes"
    assert data[0]["candidates_count"] == 2

    # Test Rich/text output
    result_text = run_cli(tmp_path, "source", "list")
    assert "Physics Notes" in result_text.stdout
    assert "src_test" in result_text.stdout
    assert "2" in result_text.stdout


def test_source_show_text_and_json(tmp_path):
    setup_test_data(tmp_path)

    # Test JSON output
    result_json = run_cli(tmp_path, "--json", "source", "show", "src_test")
    data = json.loads(result_json.stdout)
    assert data["id"] == "src_test"
    assert data["title"] == "Physics Notes"
    assert data["candidates_count"] == 2
    assert "Force equals mass times acceleration" in data["content"]

    # Test Rich/text output
    result_text = run_cli(tmp_path, "source", "show", "src_test")
    assert "Physics Notes" in result_text.stdout
    assert "Force equals mass times acceleration" in result_text.stdout

    # Test show non-existent source
    res_err = run_cli(tmp_path, "source", "show", "src_nonexistent", check=False)
    assert res_err.returncode != 0
    assert "unknown source" in res_err.stderr


def test_source_topics_text_and_json(tmp_path):
    setup_test_data(tmp_path)

    # Test JSON output
    result_json = run_cli(tmp_path, "--json", "source", "topics", "src_test")
    data = json.loads(result_json.stdout)
    assert len(data) == 2
    assert data[0]["topic_path"] == "physics.newton.fma"
    assert data[0]["candidates_count"] == 1
    assert data[1]["topic_path"] == "physics.newton.gravity"
    assert data[1]["candidates_count"] == 1

    # Test Rich/text output
    result_text = run_cli(tmp_path, "source", "topics", "src_test")
    assert "physics.newton.fma" in result_text.stdout
    assert "physics.newton.gravity" in result_text.stdout


def test_source_candidates_text_and_json(tmp_path):
    setup_test_data(tmp_path)

    # Test JSON output (no topic filter)
    result_json = run_cli(tmp_path, "--json", "source", "candidates", "src_test")
    data = json.loads(result_json.stdout)
    assert len(data) == 2
    assert data[0]["id"] == "cand_physics_1"
    assert data[1]["id"] == "cand_physics_2"

    # Test JSON output (with topic filter)
    result_json_filtered = run_cli(tmp_path, "--json", "source", "candidates", "src_test", "--topic", "physics.newton.gravity")
    data_filtered = json.loads(result_json_filtered.stdout)
    assert len(data_filtered) == 1
    assert data_filtered[0]["id"] == "cand_physics_2"

    # Test Rich/text output
    result_text = run_cli(tmp_path, "source", "candidates", "src_test")
    assert "cand_physics_1" in result_text.stdout
    assert "cand_physics_2" in result_text.stdout


def test_source_review_non_blocking_error(tmp_path):
    setup_test_data(tmp_path)

    # In non-interactive mode or with --json, dojo source review should exit with error
    result = run_cli(tmp_path, "--json", "source", "review", "src_test", check=False)
    assert result.returncode != 0
    assert "source review requires interactive terminal" in result.stderr

    result_no_input = run_cli(tmp_path, "--no-input", "source", "review", "src_test", check=False)
    assert result_no_input.returncode != 0
    assert "source review requires interactive terminal" in result_no_input.stderr


def test_queue_candidate_by_id(tmp_path):
    setup_test_data(tmp_path)

    # Queue first candidate
    out = run_cli(tmp_path, "--json", "queue", "cand_physics_1").stdout
    res = json.loads(out)
    assert res["ok"] is True
    assert res["data"]["promoted_count"] == 1
    assert res["data"]["promoted_ids"] == ["ex_physics_1"]

    # Verify state in DB
    db_path = tmp_path / "dojo.sqlite3"
    with db.connect(db_path) as session:
        # Candidate 1 should be gone
        assert db.get_candidate(session, "cand_physics_1") is None
        # Candidate 2 should still exist
        assert db.get_candidate(session, "cand_physics_2") is not None
        
        # Exercise should exist
        from sqlmodel import select
        from dojo.db import Exercise
        ex = session.exec(select(Exercise).where(Exercise.id == "ex_physics_1")).first()
        assert ex is not None
        assert ex.prompt == "What is F=ma?"
        assert ex.topic_path == "physics.newton.fma"


def test_queue_source_bulk(tmp_path):
    setup_test_data(tmp_path)

    # Queue source bulk with limit = 1
    out = run_cli(tmp_path, "--json", "queue", "--source", "src_test", "--limit", "1").stdout
    res = json.loads(out)
    assert res["ok"] is True
    assert res["data"]["promoted_count"] == 1
    
    # One candidate should remain, one should be promoted
    db_path = tmp_path / "dojo.sqlite3"
    with db.connect(db_path) as session:
        candidates = db.list_candidates(session, "src_test")
        assert len(candidates) == 1


def test_queue_source_by_topic(tmp_path):
    setup_test_data(tmp_path)

    # Queue source by topic path
    out = run_cli(tmp_path, "--json", "queue", "--source", "src_test", "--topic", "physics.newton.gravity").stdout
    res = json.loads(out)
    assert res["ok"] is True
    assert res["data"]["promoted_count"] == 1
    
    db_path = tmp_path / "dojo.sqlite3"
    with db.connect(db_path) as session:
        # gravity candidate should be promoted, fma should still exist
        assert db.get_candidate(session, "cand_physics_2") is None
        assert db.get_candidate(session, "cand_physics_1") is not None
