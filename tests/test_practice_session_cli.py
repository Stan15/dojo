import json
import os
import subprocess
import sys
import time
from pathlib import Path
from dojo import db


from helpers import run_cli


def setup_test_data(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    db.init_db(db_path)
    with db.connect(db_path) as session:
        # Save a source
        db.save_source(
            session,
            id="src_1",
            title="Geography",
            content="Paris is the capital of France. Berlin is the capital of Germany.",
            kind="text",
        )
        
        # Save exercises
        db.save_candidate(
            session,
            id="cand_1",
            source_id="src_1",
            prompt="Capital of France?",
            answer="Paris",
            topic_path="geo.france",
            source_refs={"span": "Paris"},
        )
        db.save_candidate(
            session,
            id="cand_2",
            source_id="src_1",
            prompt="Capital of Germany?",
            answer="Berlin",
            topic_path="geo.germany",
            source_refs={"span": "Berlin"},
        )
        
        # Promote them to exercises
        db.promote_candidate(session, "cand_1")
        db.promote_candidate(session, "cand_2")
    return db_path


def test_start_session(tmp_path):
    setup_test_data(tmp_path)

    # Start practice session
    out = run_cli(tmp_path, "--json", "start").stdout
    res = json.loads(out)
    assert res["ok"] is True
    assert res["type"] == "practice_session_started"
    assert res["data"]["status"] == "active"
    assert len(res["data"]["exercise_ids"]) == 2
    assert res["data"]["current_index"] == 0

    # Resume practice session (by default starting a second time without --reset resumes)
    out_resume = run_cli(tmp_path, "--json", "start").stdout
    res_resume = json.loads(out_resume)
    assert res_resume["type"] == "practice_session_resumed"
    assert res_resume["data"]["id"] == res["data"]["id"]

    # Reset session
    out_reset = run_cli(tmp_path, "--json", "start", "--reset").stdout
    res_reset = json.loads(out_reset)
    assert res_reset["type"] == "practice_session_started"
    assert res_reset["data"]["id"] != res["data"]["id"]


def test_ready_reveal_prompt(tmp_path):
    setup_test_data(tmp_path)
    run_cli(tmp_path, "start")

    # Reveal prompt
    out = run_cli(tmp_path, "--json", "ready").stdout
    res = json.loads(out)
    assert res["session_id"].startswith("sess_")
    assert res["exercise_id"] == "ex_1"
    assert res["prompt"] == "Capital of France?"
    assert res["started_at"] is not None


def test_answer_correct_and_incorrect(tmp_path):
    setup_test_data(tmp_path)
    run_cli(tmp_path, "start")

    # Trying to answer before ready should raise error
    err_res = run_cli(tmp_path, "answer", "Paris", check=False)
    assert err_res.returncode != 0
    assert "prompt not revealed yet" in err_res.stderr

    # Ready first
    run_cli(tmp_path, "ready")
    time.sleep(0.5)

    # Answer correctly
    out_correct = run_cli(tmp_path, "--json", "answer", "Paris").stdout
    res_correct = json.loads(out_correct)
    assert res_correct["score"] == 1.0
    assert res_correct["latency_seconds"] > 0
    assert res_correct["is_session_completed"] is False
    assert res_correct["next_index"] == 1

    # Ready next
    run_cli(tmp_path, "ready")

    # Answer incorrectly
    out_incorrect = run_cli(tmp_path, "--json", "answer", "WrongAnswer").stdout
    res_incorrect = json.loads(out_incorrect)
    assert res_incorrect["score"] == 0.0
    assert res_incorrect["is_session_completed"] is True


def test_progress_stats(tmp_path):
    setup_test_data(tmp_path)
    run_cli(tmp_path, "start")

    # Exercise 1
    run_cli(tmp_path, "ready")
    run_cli(tmp_path, "answer", "Paris")

    # Exercise 2
    run_cli(tmp_path, "ready")
    run_cli(tmp_path, "answer", "Wrong")

    # Run progress
    out = run_cli(tmp_path, "--json", "progress").stdout
    res = json.loads(out)
    assert res["total_attempts"] == 2
    assert res["average_score"] == 0.5
    assert len(res["recent_attempts"]) == 2


def test_due_cli(tmp_path):
    setup_test_data(tmp_path)
    
    # Check initial due count
    out = run_cli(tmp_path, "--json", "due").stdout
    res = json.loads(out)
    assert res["due_count"] == 2
    
    # Filter by topic that matches
    out_topic = run_cli(tmp_path, "--json", "due", "--topic", "geo.france").stdout
    res_topic = json.loads(out_topic)
    assert res_topic["due_count"] == 1
    
    # Filter by topic that does not match
    out_none = run_cli(tmp_path, "--json", "due", "--topic", "math").stdout
    res_none = json.loads(out_none)
    assert res_none["due_count"] == 0


def test_skip_cli(tmp_path):
    setup_test_data(tmp_path)
    run_cli(tmp_path, "start")
    run_cli(tmp_path, "ready")
    
    # Skip the active exercise
    out = run_cli(tmp_path, "--json", "skip", "--reason", "forgot", "--feedback", "forgot france capital").stdout
    res = json.loads(out)
    assert res["skip_reason"] == "forgot"
    assert res["feedback"] == "forgot france capital"
    assert res["is_session_completed"] is False
    assert res["next_index"] == 1


def test_correct_cli(tmp_path):
    setup_test_data(tmp_path)
    run_cli(tmp_path, "start")
    run_cli(tmp_path, "ready")
    run_cli(tmp_path, "answer", "Wrong") # Incorrect answer recorded
    
    # Correct it using CLI
    out = run_cli(tmp_path, "--json", "correct", "--feedback", "typo override").stdout
    res = json.loads(out)
    assert res["score"] == 1.0
    assert res["feedback"] == "typo override"
