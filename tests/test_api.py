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


def test_custom_instructions_configuration(tmp_path):
    from unittest.mock import patch
    from dojo.connectors import CommandConnectorResult

    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)

    # Ingest source
    res = api.add_source(title="S", content="C", kind="text")
    source_id = res["source_id"]

    # Configure custom prompts
    api.save_config("prompt.exercise_generate_instructions", "Custom JIT instructions.")
    api.save_config("prompt.profile_consolidate_instructions", "Custom consolidate instructions.")

    # Verify JIT uses custom instructions
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
                        "prompt": "Q",
                        "answer": "A",
                        "topic_path": "T",
                        "source_refs": [{"source_id": source_id, "span": {"start_line": 1, "end_line": 1, "anchor_text": "C"}}]
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
                        "prompt": "Q",
                        "answer": "A",
                        "topic_path": "T",
                        "source_refs": [{"source_id": source_id, "span": {"start_line": 1, "end_line": 1, "anchor_text": "C"}}]
                    }
                ]
            }
        )
        api.start_practice_session(limit=1)
        assert mock_invoke.call_count == 1

        # Call is JIT generation
        req_jit = mock_invoke.call_args[0][1]
        assert req_jit["task"] == "exercise.generate"
        assert "Custom JIT instructions." in req_jit["instructions"]
        assert req_jit["source"]["content"] == "C"

    # Verify consolidate uses custom instructions when called directly
    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
            status="ok",
            connector_name="mock-agent",
            input_mode="stdin-prompt",
            output_mode="stdout-json-or-text",
            request={},
            raw_stdout=json.dumps({"hypotheses": []}),
            raw_stderr="",
            stderr_tail="",
            exit_code=0,
            duration_seconds=0.1,
            parse_status="json",
            parsed_stdout={"hypotheses": []}
        )
        # Create an attempt
        api.reveal_prompt()
        api.submit_answer("A")

        api.consolidate_learner_profile()
        assert mock_invoke.call_count == 1
        call_args = mock_invoke.call_args[0]
        req = call_args[1]
        assert req["instructions"] == "Custom consolidate instructions."


def test_feedback_automatic_routing(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)

    # Create Campaign
    with db.connect(db_path) as session:
        campaign = db.Campaign(
            id="camp_git",
            name="Git Campaign",
            topic_path="git",
            mission="Master Git",
            attack_plan_json="[]",
            strategy_profile_json='{"mode": "practice"}',
        )
        session.add(campaign)
        session.commit()

    res = api.add_source(title="S", content="C", kind="text")
    source_id = res["source_id"]
    api.save_candidate(
        id="cand_1",
        source_id=source_id,
        prompt="P1",
        answer="A1",
        topic_path="git.basics",
        source_refs={"span": "C"},
    )
    api.promote_source_topic(source_id)
    api.start_practice_session(limit=1)
    api.reveal_prompt()
    api.submit_answer("A1")

    # Log feedback
    feedback = api.add_learner_feedback("Very confusing explanation")
    assert feedback["topic_path"] == "git"
    assert feedback["description"] == "Very confusing explanation"
    assert feedback["key"].startswith("feedback.user.")


def test_consolidate_updates_campaign_strategy(tmp_path):
    from unittest.mock import patch
    from dojo.connectors import CommandConnectorResult

    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)

    # Create Campaign
    with db.connect(db_path) as session:
        campaign = db.Campaign(
            id="camp_git",
            name="Git Campaign",
            topic_path="git",
            mission="Master Git",
            attack_plan_json="[]",
            strategy_profile_json='{"mode": "practice"}',
        )
        session.add(campaign)
        session.commit()

    # Add attempt mapped to campaign
    res = api.add_source(title="S", content="C", kind="text")
    source_id = res["source_id"]
    api.save_candidate(
        id="cand_1",
        source_id=source_id,
        prompt="P1",
        answer="A1",
        topic_path="git.basics",
        source_refs={"span": "C"},
    )
    api.promote_source_topic(source_id)
    api.start_practice_session(limit=1)
    api.reveal_prompt()
    api.submit_answer("wrong")

    # Mock LLM consolidation return
    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
            status="ok",
            connector_name="mock-agent",
            input_mode="stdin-prompt",
            output_mode="stdout-json-or-text",
            request={},
            raw_stdout=json.dumps({
                "refined_mission": "Master Git and branching",
                "calibrated_strategy": {"mode": "diagnostic", "difficulty": "intermediate"},
                "hypotheses": [
                    {"key": "misconception.git_reset", "description": "Confused about reset vs checkout"}
                ]
            }),
            raw_stderr="",
            stderr_tail="",
            exit_code=0,
            duration_seconds=0.1,
            parse_status="json",
            parsed_stdout={
                "refined_mission": "Master Git and branching",
                "calibrated_strategy": {"mode": "diagnostic", "difficulty": "intermediate"},
                "hypotheses": [
                    {"key": "misconception.git_reset", "description": "Confused about reset vs checkout"}
                ]
            }
        )

        consolidate_res = api.consolidate_learner_profile(campaign_id="camp_git")
        assert consolidate_res["status"] == "ok"

    # Verify DB updates
    with db.connect(db_path) as session:
        camp = session.get(db.Campaign, "camp_git")
        assert camp.mission == "Master Git and branching"
        strategy = json.loads(camp.strategy_profile_json)
        assert strategy["mode"] == "diagnostic"
        assert strategy["difficulty"] == "intermediate"


def test_correction_resets_consolidation_status(tmp_path):
    from unittest.mock import patch
    from dojo.connectors import CommandConnectorResult
    from sqlmodel import select

    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)

    # Create Campaign
    with db.connect(db_path) as session:
        campaign = db.Campaign(
            id="camp_git",
            name="Git Campaign",
            topic_path="git",
            mission="Master Git",
            attack_plan_json="[]",
            strategy_profile_json='{"mode": "practice"}',
        )
        session.add(campaign)
        session.commit()

    res = api.add_source(title="S", content="C", kind="text")
    source_id = res["source_id"]
    api.save_candidate(
        id="cand_1",
        source_id=source_id,
        prompt="P1",
        answer="A1",
        topic_path="git.basics",
        source_refs={"span": "C"},
    )
    api.promote_source_topic(source_id)
    api.start_practice_session(limit=1)
    api.reveal_prompt()
    api.submit_answer("A1")

    # Mock LLM consolidation return
    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
            status="ok",
            connector_name="mock-agent",
            input_mode="stdin-prompt",
            output_mode="stdout-json-or-text",
            request={},
            raw_stdout=json.dumps({"hypotheses": []}),
            raw_stderr="",
            stderr_tail="",
            exit_code=0,
            duration_seconds=0.1,
            parse_status="json",
            parsed_stdout={"hypotheses": []}
        )
        api.consolidate_learner_profile(campaign_id="camp_git")

    # Verify attempt is consolidated
    with db.connect(db_path) as session:
        att = session.exec(select(db.Attempt)).first()
        assert att.consolidated is True

    # Correct it with a custom score and feedback
    corrected = api.correct_last_attempt(score=0.8, feedback="partial grade")
    assert corrected["score"] == 0.8
    assert corrected["feedback"] == "partial grade"
    assert corrected["consolidated"] is False


def test_multiple_campaigns_interleaved_consolidation(tmp_path):
    from unittest.mock import patch
    from dojo.connectors import CommandConnectorResult

    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)

    # Create Campaigns
    with db.connect(db_path) as session:
        session.add(db.Campaign(
            id="camp_git",
            name="Git Campaign",
            topic_path="git",
            mission="Master Git",
            attack_plan_json="[]",
            strategy_profile_json='{"mode": "practice"}',
        ))
        session.add(db.Campaign(
            id="camp_sql",
            name="SQL Campaign",
            topic_path="sql",
            mission="Master SQL",
            attack_plan_json="[]",
            strategy_profile_json='{"mode": "practice"}',
        ))
        session.commit()

    # Generate exercises for both
    res = api.add_source(title="S", content="C", kind="text")
    source_id = res["source_id"]
    api.save_candidate(
        id="cand_git",
        source_id=source_id,
        prompt="Git Q",
        answer="Git A",
        topic_path="git.basics",
        source_refs={"span": "C"},
    )
    api.save_candidate(
        id="cand_sql",
        source_id=source_id,
        prompt="SQL Q",
        answer="SQL A",
        topic_path="sql.select",
        source_refs={"span": "C"},
    )
    api.promote_source_topic(source_id)

    # 1. Run git attempt
    api.start_practice_session(topic="git", limit=1)
    api.reveal_prompt()
    api.submit_answer("Git A")

    # 2. Run sql attempt
    api.start_practice_session(topic="sql", limit=1, reset=True)
    api.reveal_prompt()
    api.submit_answer("SQL A")

    # Mock connector
    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
            status="ok",
            connector_name="mock-agent",
            input_mode="stdin-prompt",
            output_mode="stdout-json-or-text",
            request={},
            raw_stdout=json.dumps({"hypotheses": []}),
            raw_stderr="",
            stderr_tail="",
            exit_code=0,
            duration_seconds=0.1,
            parse_status="json",
            parsed_stdout={"hypotheses": []}
        )

        # Consolidate all
        res = api.consolidate_learner_profile(campaign_id=None)
        assert res["status"] == "ok"
        assert len(res["campaigns"]) == 2

        # Both campaigns should have ran consolidation because they had unconsolidated attempts
        assert mock_invoke.call_count == 2

    # Running consolidate again should skip both since attempts are now consolidated
    res_skipped = api.consolidate_learner_profile(campaign_id=None)
    assert res_skipped["status"] == "ok"
    assert len(res_skipped["campaigns"]) == 2
    assert res_skipped["campaigns"][0]["status"] == "skipped"
    assert res_skipped["campaigns"][1]["status"] == "skipped"


def test_feedback_routing_without_guessing(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)

    # Create Campaign
    with db.connect(db_path) as session:
        campaign = db.Campaign(
            id="camp_git",
            name="Git Campaign",
            topic_path="git",
            mission="Master Git",
            attack_plan_json="[]",
            strategy_profile_json='{"mode": "practice"}',
        )
        session.add(campaign)
        session.commit()

    res = api.add_source(title="S", content="C", kind="text")
    source_id = res["source_id"]
    api.save_candidate(
        id="cand_1",
        source_id=source_id,
        prompt="P1",
        answer="A1",
        topic_path="git.basics",
        source_refs={"span": "C"},
    )
    api.promote_source_topic(source_id)
    api.start_practice_session(limit=1)
    api.reveal_prompt()
    api.submit_answer("A1")

    # Log feedback without attempt_id (guessing is disabled)
    feedback = api.add_learner_feedback("Great course overall!")
    assert feedback["topic_path"] == "git"
    assert feedback["attempt_id"] is None


def test_feedback_explicit_routing(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)

    # Create Campaign
    with db.connect(db_path) as session:
        campaign = db.Campaign(
            id="camp_git",
            name="Git Campaign",
            topic_path="git",
            mission="Master Git",
            attack_plan_json="[]",
            strategy_profile_json='{"mode": "practice"}',
        )
        session.add(campaign)
        session.commit()

    res = api.add_source(title="S", content="C", kind="text")
    source_id = res["source_id"]
    api.save_candidate(
        id="cand_1",
        source_id=source_id,
        prompt="P1",
        answer="A1",
        topic_path="git.basics",
        source_refs={"span": "C"},
    )
    api.promote_source_topic(source_id)
    api.start_practice_session(limit=1)
    api.reveal_prompt()
    ans = api.submit_answer("A1")
    attempt_id = ans["attempt_id"]

    # Log feedback with explicit attempt_id
    feedback = api.add_learner_feedback("This specific question has a typo", attempt_id=attempt_id)
    assert feedback["topic_path"] == "git"
    assert feedback["attempt_id"] == attempt_id


def test_consolidate_reads_exercise_context(tmp_path):
    from unittest.mock import patch
    from dojo.connectors import CommandConnectorResult

    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)

    # Create Campaign
    with db.connect(db_path) as session:
        campaign = db.Campaign(
            id="camp_git",
            name="Git Campaign",
            topic_path="git",
            mission="Master Git",
            attack_plan_json="[]",
            strategy_profile_json='{"mode": "practice"}',
        )
        session.add(campaign)
        session.commit()

    res = api.add_source(title="S", content="C", kind="text")
    source_id = res["source_id"]
    api.save_candidate(
        id="cand_1",
        source_id=source_id,
        prompt="Git prompt content",
        answer="A1",
        topic_path="git.basics",
        source_refs={"span": "C"},
    )
    api.promote_source_topic(source_id)
    api.start_practice_session(limit=1)
    api.reveal_prompt()
    ans = api.submit_answer("wrong")
    attempt_id = ans["attempt_id"]

    # Explicitly link feedback to that attempt
    api.add_learner_feedback("This explanation is weird", attempt_id=attempt_id)

    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
            status="ok",
            connector_name="mock-agent",
            input_mode="stdin-prompt",
            output_mode="stdout-json-or-text",
            request={},
            raw_stdout=json.dumps({"hypotheses": []}),
            raw_stderr="",
            stderr_tail="",
            exit_code=0,
            duration_seconds=0.1,
            parse_status="json",
            parsed_stdout={"hypotheses": []}
        )

        api.consolidate_learner_profile(campaign_id="camp_git")

        # Verify call context contains formatted attempt details
        assert mock_invoke.call_count == 1
        req = mock_invoke.call_args[0][1]
        active_hyps = req["active_hypotheses"]

        # Verify that the active hypothesis description contains the prompt text of the linked attempt
        assert len(active_hyps) == 1
        assert "This explanation is weird (Logged on Exercise: prompt='Git prompt content'" in active_hyps[0]


def test_start_session_auto_consolidates(tmp_path):
    from unittest.mock import patch
    from dojo.connectors import CommandConnectorResult

    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)

    # Create Campaign
    with db.connect(db_path) as session:
        campaign = db.Campaign(
            id="camp_git",
            name="Git Campaign",
            topic_path="git",
            mission="Master Git",
            attack_plan_json="[]",
            strategy_profile_json='{"mode": "practice"}',
        )
        session.add(campaign)
        session.commit()

    res = api.add_source(title="S", content="C", kind="text")
    source_id = res["source_id"]
    api.save_candidate(
        id="cand_1",
        source_id=source_id,
        prompt="Git prompt content",
        answer="A1",
        topic_path="git.basics",
        source_refs={"span": "C"},
    )
    api.promote_source_topic(source_id)

    # Verify starting session triggers profile consolidation
    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
            status="ok",
            connector_name="mock-agent",
            input_mode="stdin-prompt",
            output_mode="stdout-json-or-text",
            request={},
            raw_stdout=json.dumps({"hypotheses": []}),
            raw_stderr="",
            stderr_tail="",
            exit_code=0,
            duration_seconds=0.1,
            parse_status="json",
            parsed_stdout={"hypotheses": []}
        )

        # Start practice session (should auto-consolidate)
        sess = api.start_practice_session(topic="git", limit=1)
        assert sess is not None

        # Verify call count of invoke_command_connector is at least 1 (from consolidation)
        assert mock_invoke.call_count >= 1
