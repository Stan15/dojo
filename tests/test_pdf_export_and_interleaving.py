import json
from pathlib import Path
from unittest.mock import patch
from dojo.api import DojoAPI
from dojo.cli import cmd_campaign_export
from dojo.connectors import CommandConnectorResult
from dojo import db
import argparse

def test_pdf_generation(tmp_path):
    from dojo.pdf_generator import render_markdown_to_pdf
    output_pdf = tmp_path / "test_syllabus.pdf"
    
    syllabus_md = (
        "# Campaign Goal\n"
        "Master Python lists.\n\n"
        "## Phase 1 — Basics\n"
        "### Topics\n"
        "- **List Creation** and manipulation\n"
        "- *Indexing* and slicing list elements\n"
    )
    
    render_markdown_to_pdf(syllabus_md, output_pdf)
    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 0
    
    # Verify PDF magic bytes
    with open(output_pdf, "rb") as f:
        header = f.read(4)
        assert header == b"%PDF"


def test_pedagogical_journal_snapshots(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    db.init_db(db_path)

    # 1. Verify CREATE journal entry has initial snapshot keys
    campaign = api.create_campaign(goal="Python Lists")
    camp_id = campaign["campaign_id"]
    
    history = api.get_campaign_history(camp_id)
    journal = history["journal"]
    assert len(journal) == 1
    assert journal[0]["action"] == "CREATE"
    assert "syllabus_snapshot" in journal[0]
    assert "hypotheses_snapshot" in journal[0]
    assert journal[0]["syllabus_snapshot"] is None
    assert journal[0]["hypotheses_snapshot"] == []

    # 2. Add an active hypothesis, set syllabus, and trigger Phase Advancement
    with db.connect(db_path) as session:
        camp = session.get(db.Campaign, camp_id)
        camp.syllabus_markdown = "# Test Syllabus"
        camp.attack_plan_json = json.dumps([
            {
                "phase": 0,
                "topics": ["python.lists.diagnostic"],
                "criteria": {"min_attempts": 1, "min_accuracy": 0.0}
            },
            {
                "phase": 1,
                "topics": ["python.lists.basics"],
                "criteria": {"min_attempts": 2, "min_accuracy": 0.8}
            }
        ])
        session.add(camp)
        
        # Save a learner hypothesis
        hyp = db.LearnerHypothesis(
            id="hyp_1",
            key="misconception.index_error",
            description="Learner struggles with off-by-one errors",
            status="active",
            topic_path="python.lists"
        )
        session.add(hyp)
        
        # Add a qualifying attempt to pass Phase 0
        ex = db.Exercise(
            id="ex_diag_1",
            prompt="Prompt",
            topic_path="python.lists.diagnostic",
            source_refs="[]",
            quality="diagnostic"
        )
        session.add(ex)
        
        att = db.Attempt(
            id="att_1",
            session_id="sess_1",
            exercise_id="ex_diag_1",
            prompt="Prompt",
            user_answer="Answer",
            score=1.0,
            latency_seconds=2.0,
            campaign_id=camp_id,
            consolidated=False
        )
        session.add(att)
        session.commit()

    # Consolidate should trigger phase advancement and snapshotting
    # We patch invoke_command_connector because consolidate calls LLM
    mock_payload = {
        "refined_mission": "Optimized Python Lists",
        "journal_entry": {
            "action": "CALIBRATE_STRATEGY",
            "trigger": "consolidation trigger",
            "hypothesis": "Learner needs high support",
            "status": "resolved"
        },
        "hypotheses": [
            {
                "key": "misconception.index_error",
                "description": "Learner struggles with off-by-one errors",
                "topic_path": "python.lists"
            }
        ]
    }
    mock_result = CommandConnectorResult(
        status="ok",
        connector_name="mock-agent",
        input_mode="stdin-prompt",
        output_mode="stdout-json-or-text",
        request={},
        raw_stdout=json.dumps(mock_payload),
        raw_stderr="",
        stderr_tail="",
        exit_code=0,
        duration_seconds=0.1,
        parse_status="json",
        parsed_stdout=mock_payload
    )
    with patch("dojo.connectors.invoke_command_connector", return_value=mock_result):
        api.consolidate_learner_profile(camp_id)

    # Verify journal entries in database
    history = api.get_campaign_history(camp_id)
    journal = history["journal"]
    
    # We should have PHASE_ADVANCE and potentially CALIBRATE_STRATEGY entries
    assert len(journal) >= 2
    
    phase_advance_entry = next((e for e in journal if e["action"] == "PHASE_ADVANCE"), None)
    assert phase_advance_entry is not None
    assert phase_advance_entry["syllabus_snapshot"] == "# Test Syllabus"
    assert len(phase_advance_entry["hypotheses_snapshot"]) == 1
    assert phase_advance_entry["hypotheses_snapshot"][0]["key"] == "misconception.index_error"


def test_practice_session_multi_topic_filtering(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    db.init_db(db_path)

    # Create campaign and set a multi-topic phase
    campaign = api.create_campaign(goal="Math")
    camp_id = campaign["campaign_id"]
    
    with db.connect(db_path) as session:
        camp = session.get(db.Campaign, camp_id)
        camp.active_phase_index = 1
        camp.attack_plan_json = json.dumps([
            {"phase": 0, "topics": ["math.diagnostic"], "criteria": {"min_attempts": 2, "min_accuracy": 0.0}},
            {"phase": 1, "topics": ["math.arithmetic", "math.algebra"], "criteria": {"min_attempts": 5, "min_accuracy": 0.8}}
        ])
        session.add(camp)
        
        # Add 2 exercises from arithmetic and 2 from algebra
        ex1 = db.Exercise(id="ex_ari_1", prompt="1+1", topic_path="math.arithmetic", source_refs="[]")
        ex2 = db.Exercise(id="ex_ari_2", prompt="2+2", topic_path="math.arithmetic", source_refs="[]")
        ex3 = db.Exercise(id="ex_alg_1", prompt="x+1=2", topic_path="math.algebra", source_refs="[]")
        ex4 = db.Exercise(id="ex_alg_2", prompt="y-2=3", topic_path="math.algebra", source_refs="[]")
        session.add_all([ex1, ex2, ex3, ex4])
        session.commit()

    # Start practice session (needs to fetch exercises from both topics interleaved)
    # Since we have 4 exercises (> 3), JIT generation won't trigger
    session_info = api.start_practice_session(campaign_id=camp_id, limit=4)
    session_id = session_info["session"]["id"]
    
    with db.connect(db_path) as session:
        prac_session = session.get(db.PracticeSession, session_id)
        exercise_ids = json.loads(prac_session.exercise_ids_json)
        # Verify it drew exercises from both topics
        assert len(exercise_ids) == 4
        assert "ex_ari_1" in exercise_ids
        assert "ex_alg_1" in exercise_ids


def test_jit_generation_multi_topic_payload(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    db.init_db(db_path)

    # Create campaign and set a multi-topic phase
    campaign = api.create_campaign(goal="Math")
    camp_id = campaign["campaign_id"]
    
    with db.connect(db_path) as session:
        camp = session.get(db.Campaign, camp_id)
        camp.active_phase_index = 1
        camp.attack_plan_json = json.dumps([
            {"phase": 0, "topics": ["math.diagnostic"], "criteria": {"min_attempts": 2, "min_accuracy": 0.0}},
            {"phase": 1, "topics": ["math.arithmetic", "math.algebra"], "focus": "Interleave basic arithmetic with simple algebra equations.", "criteria": {"min_attempts": 5, "min_accuracy": 0.8}}
        ])
        camp.strategy_profile_json = json.dumps({"mode": "practice", "difficulty": "intermediate", "scaffolding": "medium"})
        session.add(camp)
        session.commit()

    # Start practice session with 0 due exercises -> will trigger JIT Generation
    # Mock return value of JIT exercise generate task
    mock_jit_payload = {
        "candidates": [
            {
                "prompt": "Evaluate 3 + x = 5",
                "answer": "x = 2",
                "topic_path": "math.algebra",
                "source_refs": []
            }
        ]
    }
    mock_connector_output = CommandConnectorResult(
        status="ok",
        connector_name="mock-agent",
        input_mode="stdin-prompt",
        output_mode="stdout-json-or-text",
        request={},
        raw_stdout=json.dumps(mock_jit_payload),
        raw_stderr="",
        stderr_tail="",
        exit_code=0,
        duration_seconds=0.1,
        parse_status="json",
        parsed_stdout=mock_jit_payload
    )
    
    with patch("dojo.connectors.invoke_command_connector", return_value=mock_connector_output) as mock_connector:
        api.start_practice_session(campaign_id=camp_id, limit=5)
        
        # Verify mock connector was called
        assert mock_connector.called
        call_args = mock_connector.call_args[0]
        request_payload = call_args[1]
        
        # Assert active topics and focus were passed to instructions and payload keys
        assert request_payload["task"] == "exercise.generate"
        assert "math.arithmetic" in request_payload["instructions"]
        assert "math.algebra" in request_payload["instructions"]
        assert "Interleave basic arithmetic with simple algebra equations" in request_payload["instructions"]
        assert request_payload["active_topics"] == ["math.arithmetic", "math.algebra"]
        assert request_payload["phase_focus"] == "Interleave basic arithmetic with simple algebra equations."


def test_cli_campaign_export(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    db.init_db(db_path)

    campaign = api.create_campaign(goal="French")
    camp_id = campaign["campaign_id"]
    
    # Set syllabus
    with db.connect(db_path) as session:
        camp = session.get(db.Campaign, camp_id)
        camp.syllabus_markdown = "# French Syllabus\n\n- Phase 1: Vocab\n- Phase 2: Verbs"
        session.add(camp)
        session.commit()

    output_pdf = tmp_path / "french_syllabus.pdf"
    
    # Test CLI execution
    args = argparse.Namespace(
        db=str(db_path),
        json=False,
        campaign=camp_id,
        format="pdf",
        output=str(output_pdf)
    )
    
    code = cmd_campaign_export(args)
    assert code == 0
    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 0
