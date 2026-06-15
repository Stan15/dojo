import json
import pytest
from pathlib import Path
from dojo import db
from dojo.api import DojoAPI

def test_api_source_lifecycle(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    
    # 1. Add Source
    res = api.add_source(
        title="Test Source",
        content="This is content of the test source.",
        kind="text",
        mission="Test mission"
    )
    assert res["source_id"].startswith("src_")
    assert res["title"] == "Test Source"
    assert res["kind"] == "text"
    assert res["candidates_count"] == 0
    
    source_id = res["source_id"]
    
    # 2. Get Source
    src = api.get_source(source_id)
    assert src is not None
    assert src["id"] == source_id
    assert src["title"] == "Test Source"
    assert src["kind"] == "text"
    assert src["mission"] == "Test mission"
    assert src["content"] == "This is content of the test source."
    assert src["candidates_count"] == 0
    
    # 3. List Sources
    sources = api.list_sources()
    assert len(sources) == 1
    assert sources[0]["id"] == source_id
    assert sources[0]["candidates_count"] == 0
    
    # 4. Save Candidate manually
    cand = api.save_candidate(
        id="cand_test_1",
        source_id=source_id,
        prompt="What is this test?",
        answer="A test case",
        topic_path="test.lifecycle",
        source_refs={"span": "test source"},
    )
    assert cand["id"] == "cand_test_1"
    assert cand["prompt"] == "What is this test?"
    
    # Verify candidates list
    candidates = api.get_source_candidates(source_id)
    assert len(candidates) == 1
    assert candidates[0]["id"] == "cand_test_1"
    
    # Verify topics list
    topics = api.get_source_topics(source_id)
    assert len(topics) == 1
    assert topics[0]["topic_path"] == "test.lifecycle"
    assert topics[0]["candidates_count"] == 1
    
    # 5. Get Candidate
    c = api.get_candidate("cand_test_1")
    assert c is not None
    assert c["prompt"] == "What is this test?"
    
    # 6. Remove Candidate
    removed = api.remove_candidate("cand_test_1")
    assert removed["id"] == "cand_test_1"
    assert api.get_candidate("cand_test_1") is None


def test_api_practice_session_lifecycle(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    
    # Ingest source
    res = api.add_source(
        title="Python Basics",
        content="Lists are ordered. Dicts are key-value mappings.",
        kind="text"
    )
    source_id = res["source_id"]
    
    # Add two candidates
    api.save_candidate(
        id="cand_python_1",
        source_id=source_id,
        prompt="Are lists ordered?",
        answer="Yes",
        topic_path="python.lists",
        source_refs={"span": "Lists are ordered"},
    )
    api.save_candidate(
        id="cand_python_2",
        source_id=source_id,
        prompt="What are dicts?",
        answer="Key-value mappings",
        topic_path="python.dicts",
        source_refs={"span": "Dicts are key-value mappings"},
    )
    
    # Promote candidates
    promoted = api.promote_source_topic(source_id)
    assert len(promoted) == 2
    assert promoted[0]["id"] == "ex_python_1"
    assert promoted[1]["id"] == "ex_python_2"
    
    # Start Practice Session
    sess_res = api.start_practice_session(limit=2)
    assert sess_res["is_new"] is True
    session = sess_res["session"]
    assert session["status"] == "active"
    assert session["exercise_ids"] == ["ex_python_1", "ex_python_2"]
    
    # Reveal first prompt
    prompt_res = api.reveal_prompt()
    assert prompt_res["exercise_id"] == "ex_python_1"
    assert prompt_res["prompt"] == "Are lists ordered?"
    assert prompt_res["index"] == 0
    assert prompt_res["total"] == 2
    assert prompt_res["started_at"] is not None
    
    # Try to start session again (should resume by default)
    sess_res_resume = api.start_practice_session(limit=2)
    assert sess_res_resume["is_new"] is False
    assert sess_res_resume["session"]["id"] == session["id"]
    
    # Submit correct answer
    ans_res = api.submit_answer("yes")
    assert ans_res["score"] == 1.0
    assert ans_res["is_session_completed"] is False
    assert ans_res["next_index"] == 1
    
    # Reveal second prompt
    prompt_res2 = api.reveal_prompt()
    assert prompt_res2["exercise_id"] == "ex_python_2"
    
    # Submit incorrect answer
    ans_res2 = api.submit_answer("wrong answer")
    assert ans_res2["score"] == 0.0
    assert ans_res2["is_session_completed"] is True
    
    # Verify progress metrics
    progress = api.get_progress()
    assert progress["total_attempts"] == 2
    assert progress["average_score"] == 0.5
    assert len(progress["recent_attempts"]) == 2
