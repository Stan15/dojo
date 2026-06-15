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


def test_active_queue_limit(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    
    # Ingest source
    res = api.add_source(title="S", content="C", kind="text")
    source_id = res["source_id"]
    
    # Save 21 candidates
    for i in range(21):
        api.save_candidate(
            id=f"cand_limit_{i}",
            source_id=source_id,
            prompt=f"P {i}",
            answer=f"A {i}",
            topic_path="limit",
            source_refs={"span": "C"},
        )
        
    # Promote 20 candidates
    for i in range(20):
        api.promote_candidate(f"cand_limit_{i}")
        
    # Promoting the 21st should raise ValueError due to queue limit
    with pytest.raises(ValueError) as excinfo:
        api.promote_candidate("cand_limit_20")
    assert "Active queue is full" in str(excinfo.value)


def test_skip_exercise_lifecycle(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    
    res = api.add_source(title="S", content="C", kind="text")
    source_id = res["source_id"]
    
    api.save_candidate(
        id="cand_skip_1",
        source_id=source_id,
        prompt="P1",
        answer="A1",
        topic_path="skip",
        source_refs={"span": "C"},
    )
    api.save_candidate(
        id="cand_skip_2",
        source_id=source_id,
        prompt="P2",
        answer="A2",
        topic_path="skip",
        source_refs={"span": "C"},
    )
    
    api.promote_source_topic(source_id)
    assert api.get_due_count() == 2
    
    # Start session
    sess_res = api.start_practice_session(limit=2)
    session = sess_res["session"]
    
    # Ready
    api.reveal_prompt()
    
    # Skip first with "forgot"
    skip_res = api.skip_active_exercise(reason="forgot")
    assert skip_res["skip_reason"] == "forgot"
    assert skip_res["is_session_completed"] is False
    
    # Ready second
    api.reveal_prompt()
    
    # Skip second with "too_easy"
    skip_res2 = api.skip_active_exercise(reason="too_easy")
    assert skip_res2["skip_reason"] == "too_easy"
    assert skip_res2["is_session_completed"] is True
    
    # Verify due counts:
    # "forgot" stays due, "too_easy" is archived/removed.
    # Total due should be 1 (ex_skip_1).
    assert api.get_due_count() == 1


def test_correct_last_attempt(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    
    res = api.add_source(title="S", content="C", kind="text")
    source_id = res["source_id"]
    
    api.save_candidate(
        id="cand_correct_1",
        source_id=source_id,
        prompt="P1",
        answer="A1",
        topic_path="correct",
        source_refs={"span": "C"},
    )
    api.promote_source_topic(source_id)
    
    api.start_practice_session(limit=1)
    api.reveal_prompt()
    
    # Submit incorrect answer
    ans_res = api.submit_answer("wrong")
    assert ans_res["score"] == 0.0
    
    # Correct last attempt
    corrected = api.correct_last_attempt(feedback="grader error")
    assert corrected["score"] == 1.0
    assert corrected["feedback"] == "grader error"


def test_learner_hypotheses_and_consolidation(tmp_path):
    from unittest.mock import patch
    from dojo.connectors import CommandConnectorResult
    
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    
    # Save a hypothesis manually
    hyp = api.save_learner_hypothesis(key="misconception.test", description="Manually added")
    assert hyp["key"] == "misconception.test"
    assert hyp["description"] == "Manually added"
    assert hyp["status"] == "active"
    
    # List active hypotheses
    active_hyps = api.get_learner_hypotheses(status="active")
    assert len(active_hyps) == 1
    assert active_hyps[0]["key"] == "misconception.test"
    
    # Mock connector output for profile consolidation
    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
            status="ok",
            connector_name="mock-agent",
            input_mode="stdin-prompt",
            output_mode="stdout-json-or-text",
            request={},
            raw_stdout=json.dumps({
                "hypotheses": [
                    {"key": "misconception.consolidated", "description": "Synthesized misconception"}
                ]
            }),
            raw_stderr="",
            stderr_tail="",
            exit_code=0,
            duration_seconds=0.1,
            parse_status="json",
            parsed_stdout={
                "hypotheses": [
                    {"key": "misconception.consolidated", "description": "Synthesized misconception"}
                ]
            }
        )
        
        res = api.consolidate_learner_profile()
        assert res["status"] == "ok"
        assert len(res["hypotheses"]) == 1
        assert res["hypotheses"][0]["key"] == "misconception.consolidated"
        assert res["hypotheses"][0]["description"] == "Synthesized misconception"
        
        # Verify that the manual hypothesis 'misconception.test' was resolved (archived)
        active_hyps_after = api.get_learner_hypotheses(status="active")
        assert len(active_hyps_after) == 1
        assert active_hyps_after[0]["key"] == "misconception.consolidated"
        
        resolved_hyps = api.get_learner_hypotheses(status="resolved")
        assert len(resolved_hyps) == 1
        assert resolved_hyps[0]["key"] == "misconception.test"


def test_diagnostic_question_lifecycle(tmp_path):
    from unittest.mock import patch
    from dojo.connectors import CommandConnectorResult
    
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    
    # Ingest source
    res = api.add_source(title="S", content="C", kind="text")
    source_id = res["source_id"]
    
    # Mock connector output to return a diagnostic question
    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
            status="ok",
            connector_name="mock-agent",
            input_mode="stdin-prompt",
            output_mode="stdout-json-or-text",
            request={},
            raw_stdout=json.dumps({
                "candidates": [
                    {
                        "prompt": "What is your main goal?",
                        "answer": None,
                        "topic_path": "diag",
                        "source_refs": [{"source_id": source_id, "span": {"start_line": 1, "end_line": 1, "anchor_text": "C"}}],
                        "quality": "diagnostic"
                    }
                ]
            }),
            raw_stderr="",
            stderr_tail="",
            exit_code=0,
            duration_seconds=0.1,
            parse_status="json",
            parsed_stdout={
                "candidates": [
                    {
                        "prompt": "What is your main goal?",
                        "answer": None,
                        "topic_path": "diag",
                        "source_refs": [{"source_id": source_id, "span": {"start_line": 1, "end_line": 1, "anchor_text": "C"}}],
                        "quality": "diagnostic"
                    }
                ]
            }
        )
        
        # Start practice session (triggers JIT because due count is 0)
        sess_res = api.start_practice_session(limit=1)
        session = sess_res["session"]
        assert len(session["exercise_ids"]) == 1
        
        # Reveal prompt
        prompt_res = api.reveal_prompt()
        assert prompt_res["prompt"] == "What is your main goal?"
        
        # Submit answer (diagnostic prompt has no answer, so any answer is correct)
        ans_res = api.submit_answer("I want to learn code writing.")
        assert ans_res["score"] == 1.0
        
    # Now verify that consolidate_learner_profile parses diagnostic attempt
    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
            status="ok",
            connector_name="mock-agent",
            input_mode="stdin-prompt",
            output_mode="stdout-json-or-text",
            request={},
            raw_stdout=json.dumps({
                "hypotheses": [
                    {"key": "preference.practical_code", "description": "Learner wants practical code templates"}
                ]
            }),
            raw_stderr="",
            stderr_tail="",
            exit_code=0,
            duration_seconds=0.1,
            parse_status="json",
            parsed_stdout={
                "hypotheses": [
                    {"key": "preference.practical_code", "description": "Learner wants practical code templates"}
                ]
            }
        )
        
        consolidate_res = api.consolidate_learner_profile()
        assert consolidate_res["status"] == "ok"
        assert len(consolidate_res["hypotheses"]) == 1
        assert consolidate_res["hypotheses"][0]["key"] == "preference.practical_code"
        
        # Verify it is active in the database
        active = api.get_learner_hypotheses(status="active")
        assert len(active) == 1
        assert active[0]["key"] == "preference.practical_code"


