from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from contextlib import redirect_stdout, redirect_stderr
import pytest

from dojo.schemas import (
    Source,
    Campaign,
    Exercise,
    Candidate,
    Attempt,
    Insight,
    PracticeSession,
    AttackPlanPhase,
    CriteriaEntry
)
from dojo.store import DojoStore, slugify
from dojo.api import DojoAPI
from dojo.connectors import CommandConnectorResult
from dojo.cli import main

# ==========================================
# Mock Git Operations Globally
# ==========================================

@pytest.fixture(autouse=True)
def mock_git_operations():
    with patch("dojo.store.engine.init_git") as mock_init, patch("dojo.store.engine.commit_git") as mock_commit:
        yield mock_init, mock_commit


# ==========================================
# CLI Runner Helper
# ==========================================

class MockCompletedProcess:
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_cli(tmp_path: Path, *args: str, check: bool = True) -> MockCompletedProcess:
    cli_args = ["--db", str(tmp_path)] + list(args)
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    returncode = 0
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            try:
                ret = main(cli_args)
                if ret is not None:
                    returncode = ret
            except SystemExit as exc:
                if isinstance(exc.code, int):
                    returncode = exc.code
                elif exc.code is None:
                    returncode = 0
                else:
                    returncode = 1
                    stderr_buf.write(str(exc.code))
    except Exception as e:
        returncode = 1
        stderr_buf.write(str(e))
        
    stdout = stdout_buf.getvalue()
    stderr = stderr_buf.getvalue()
    
    if check and returncode != 0:
        raise AssertionError(f"command failed: {cli_args}\nstdout={stdout}\nstderr={stderr}")
        
    return MockCompletedProcess(returncode, stdout, stderr)


# ==========================================
# Test Fixtures & Mock Results
# ==========================================

MOCK_SMOKE_TEST = "OK"

MOCK_DIAGNOSTIC_RESPONSE = {
    "title": "Grounded French Campaign",
    "base_topic": "language.french.tef",
    "diagnostic_questions": [
        "What is your comfort level with French oral comprehension?",
        "Do you have a strict deadline for TEF preparation?"
    ]
}

MOCK_JIT_RESPONSE = {
    "thinking": "Creating calibration exercises.",
    "topic_span": {
        "existing_topic": "language.french.tef",
        "active_topics_covered": ["language.french.tef"],
        "mission_alignment": "onboarding calibration questions",
        "note": "calibrating level"
    },
    "exercise_draft": {
        "set_title": "Initial Diagnostics",
        "target_outcome": "accuracy baseline",
        "candidates": [
            {
                "prompt": "Describe a rental ad question.",
                "topic_path": "language.french.tef",
                "difficulty": "intermediate",
                "answer": "Ask for utility costs.",
                "rubric": "Checks location and pricing."
            },
            {
                "prompt": "Ask location details of an apartment.",
                "topic_path": "language.french.tef",
                "difficulty": "intermediate",
                "answer": "Where is it located?",
                "rubric": "Checks question structure."
            }
        ]
    }
}

MOCK_CONSOLIDATE_RESPONSE = {
    "thinking": "Analyzing answers to onboarding questions.",
    "hypotheses": [
        {
            "key": "preference.scaffolding_oral",
            "description": "Learner requests heavy scaffolding for complex grammar.",
            "topic_path": "language.french.tef"
        }
    ],
    "refined_mission": "Acquire NCLC 7 in TEF Canada",
    "calibrated_strategy": {
        "mode": "practice",
        "difficulty": "intermediate",
        "scaffolding": "medium"
    },
    "revised_attack_plan": [
        {
            "phase": 1,
            "topics": ["language.french.tef.expression_orale.part_a"],
            "criteria": {"min_attempts": 3, "min_accuracy": 0.8},
            "focus": "Oral expression part A"
        },
        {
            "phase": 2,
            "topics": ["language.french.tef.expression_orale.part_b"],
            "criteria": {"min_attempts": 3, "min_accuracy": 0.8},
            "focus": "Oral expression part B Argumentation"
        }
    ],
    "syllabus_markdown": "# Grounded French Syllabus\n\n- Phase 1: Oral A\n- Phase 2: Oral B",
    "source_topic_mappings": {
        "src_french": ["language.french.tef"]
    },
    "journal_entry": {
        "action": "CALIBRATE_STRATEGY",
        "trigger": "onboarding complete",
        "status": "resolved",
        "hypothesis": "learner is intermediate but needs oral scaffolding"
    }
}


def make_mock_result(status: str, parsed: Any, raw: str = "") -> CommandConnectorResult:
    return CommandConnectorResult(
        status=status,
        connector_name="mock_connector",
        input_mode="stdin-prompt",
        output_mode="stdout-json-or-text",
        request={},
        raw_stdout=raw or json.dumps(parsed),
        raw_stderr="",
        stderr_tail="",
        exit_code=0,
        duration_seconds=0.5,
        parse_status="ok" if status == "ok" else "error",
        parsed_stdout=parsed if status == "ok" else None,
        error=None if status == "ok" else "error occurred"
    )


# ==========================================
# Schema Tests
# ==========================================

def test_pydantic_exclude_defaults_frontmatter(tmp_path: Path):
    store = DojoStore(tmp_path)
    
    # Save a source note, check defaults omission
    source = Source(
        id="src_test",
        title="Test Source",
        kind="text",
        content="Test content lines here."
    )
    store.save_source(source)
    
    source_file = tmp_path / "sources" / "src_test.md"
    assert source_file.exists()
    content = source_file.read_text(encoding="utf-8")
    
    # Default parameters should not be serialized
    assert "mission:" not in content
    assert "path:" not in content
    
    # Reload and check values
    reloaded = store.get_source("src_test")
    assert reloaded is not None
    assert reloaded.title == "Test Source"
    assert reloaded.mission is None
    assert reloaded.content == "Test content lines here."


# ==========================================
# Store Tests
# ==========================================

def test_store_atomic_write_and_locking(tmp_path: Path):
    store = DojoStore(tmp_path)
    
    # Perform standard writes, verify lock file exists during transaction
    campaign = Campaign(
        id="test",
        name="Test Campaign",
        mission="Succeed"
    )
    store.save_campaign(campaign)
    
    campaign_file = tmp_path / "campaigns" / "camp_test" / "campaign.md"
    assert campaign_file.exists()
    
    # Locking is transient, but make sure dojo.lock is created or managed
    assert (tmp_path / "dojo.lock").exists()


def test_store_incremental_index_sync(tmp_path: Path):
    store = DojoStore(tmp_path)
    
    source = Source(
        id="src_1",
        title="Source One",
        kind="text",
        content="Hello source text"
    )
    store.save_source(source)
    
    # Check index cache created
    index_file = tmp_path / ".index.json"
    assert index_file.exists()
    
    # Reload index directly
    index_data = json.loads(index_file.read_text(encoding="utf-8"))
    assert "sources/src_1.md" in index_data["files"]
    
    # Modify file mtime artificially, reload
    file_path = tmp_path / "sources" / "src_1.md"
    os.utime(file_path, (file_path.stat().st_atime, file_path.stat().st_mtime - 100))
    
    # Reload store
    store2 = DojoStore(tmp_path)
    assert store2.get_source("src_1").title == "Source One"


# ==========================================
# API Integration Tests
# ==========================================

@patch("dojo.connectors.invoke_command_connector")
def test_api_onboarding_practice_loop(mock_invoke: MagicMock, tmp_path: Path):
    # Setup mock returns
    mock_invoke.side_effect = [
        make_mock_result("ok", MOCK_DIAGNOSTIC_RESPONSE), # JIT generation diagnostic questions
        make_mock_result("ok", MOCK_CONSOLIDATE_RESPONSE)  # Reflection/consolidation profile
    ]
    
    api = DojoAPI(tmp_path)
    
    # Create Campaign
    campaign_meta = api.create_campaign(
        name="French Oral prep",
        topic_path="language.french.tef",
        mission="Reach NCLC 7 level"
    )
    campaign_id = campaign_meta["id"]
    
    # Initial strategy and plan override for diagnostic onboarding
    campaign = api.store.get_campaign(campaign_id)
    assert campaign is not None
    campaign.strategy_profile = {"mode": "diagnostic", "difficulty": "intermediate", "scaffolding": "medium"}
    campaign.attack_plan = [
        AttackPlanPhase(
            phase=0,
            topics=[f"language.french.tef.diagnostic"],
            criteria=CriteriaEntry(min_attempts=2, min_accuracy=0.0)
        )
    ]
    api.store.save_campaign(campaign)
    
    # Start onboarding practice session
    sess_res = api.start_practice_session(campaign_id=campaign_id)
    assert sess_res["is_new"] is True
    session_id = sess_res["session"]["id"]
    exercise_ids = sess_res["session"]["exercise_ids"]
    
    assert len(exercise_ids) == 2
    
    # Practice Q1
    prompt_q1 = api.reveal_prompt(session_id=session_id)
    assert prompt_q1["exercise_id"] == exercise_ids[0]
    ans_q1 = api.submit_answer(user_answer="Yes, I am intermediate.", session_id=session_id)
    assert ans_q1["is_session_completed"] is False
    
    # Practice Q2
    prompt_q2 = api.reveal_prompt(session_id=session_id)
    assert prompt_q2["exercise_id"] == exercise_ids[1]
    ans_q2 = api.submit_answer(user_answer="I have 2 months.", session_id=session_id)
    assert ans_q2["is_session_completed"] is True
    
    # Verify session completion
    active_sess = api.get_active_practice_session()
    assert active_sess is None
    
    # Consolidate / reflect
    consolidate_res = api.consolidate_learner_profile(campaign_id=campaign_id)
    assert "preference.scaffolding_oral" in [h["key"] for h in consolidate_res["insights"]]
    
    # Syllabus check
    reloaded_camp = api.store.get_campaign(campaign_id)
    assert "Phase 1: Oral A" in reloaded_camp.syllabus_markdown
    assert reloaded_camp.active_phase_index == 0 # starts at 0, revised plan phases are 1 and 2


@patch("dojo.connectors.invoke_command_connector")
def test_api_insight_merging(mock_invoke: MagicMock, tmp_path: Path):
    api = DojoAPI(tmp_path)
    
    campaign = api.create_campaign(
        name="Math Campaign",
        topic_path="math.calc",
        mission="Master integration"
    )
    campaign_id = campaign["id"]
    
    # 1. Manually save an active insight
    insight1 = Insight(
        id="ins_test_1",
        key="preference.scaffolding_level",
        description="Prefers high scaffolding",
        sources=["campaigns/camp_math-calc/attempts/att_1.md"]
    )
    api.store.save_insight(campaign_id, insight1)
    
    # 2. Mock profile consolidate returning the same insight key
    MOCK_MERGE_RESPONSE = {
        "thinking": "Updating scaffolding preference.",
        "hypotheses": [
            {
                "key": "preference.scaffolding_level",
                "description": "Prefers medium scaffolding based on recent correct answers.",
                "topic_path": "math.calc"
            }
        ],
        "refined_mission": "Master integration",
        "calibrated_strategy": {
            "mode": "practice",
            "difficulty": "intermediate",
            "scaffolding": "medium"
        },
        "revised_attack_plan": [
            {
                "phase": 1,
                "topics": ["math.calc"],
                "criteria": {"min_attempts": 3, "min_accuracy": 0.8}
            }
        ],
        "syllabus_markdown": "# Math Syllabus",
        "journal_entry": {
            "action": "CALIBRATE_STRATEGY",
            "trigger": "new attempts",
            "status": "resolved",
            "hypothesis": "update scaffolding"
        }
    }
    
    mock_invoke.return_value = make_mock_result("ok", MOCK_MERGE_RESPONSE)
    
    # Create fake unreflected attempt so consolidate executes
    attempt = Attempt(
        id="att_new_1",
        session_id="sess_fake",
        exercise_id="ex_1",
        campaign_id=campaign_id,
        score=1.0,
        latency_seconds=12.5,
        reflected=False
    )
    api.store.save_attempt(campaign_id, attempt)
    
    # Consolidate
    api.consolidate_learner_profile(campaign_id=campaign_id)
    
    # Reload and check merged insights
    insights = api.store.list_insights(campaign_id)
    print("\nDEBUG INSIGHTS:", [ins.model_dump() for ins in insights])
    assert len(insights) == 1
    ins = insights[0]
    
    assert ins.key == "preference.scaffolding_level"
    assert ins.description == "Prefers medium scaffolding based on recent correct answers."
    # Should append attempt to sources
    found = False
    for src in ins.sources:
        if src.startswith("campaigns/camp_math-calc/attempts/att_") and src.endswith("_ex_1.md"):
            found = True
            break
    assert found
    assert "campaigns/camp_math-calc/attempts/att_1.md" in ins.sources


# ==========================================
# CLI Subcommand Tests
# ==========================================

@patch("dojo.connectors.invoke_command_connector")
def test_cli_e2e_workflow(mock_invoke: MagicMock, tmp_path: Path):
    mock_invoke.side_effect = [
        make_mock_result("ok", {"tested": True}),          # 1. connect ai test
        make_mock_result("ok", MOCK_DIAGNOSTIC_RESPONSE), # 2. campaign onboarding diagnostic questions
        make_mock_result("ok", MOCK_CONSOLIDATE_RESPONSE)  # 3. profile consolidate
    ]

    # Test connect ai command registration
    run_cli(tmp_path, "connect", "ai", "command", "mockagent", "--default", "--", "echo", "mock")
    
    store = DojoStore(tmp_path)
    connector = store.get_connector("mockagent")
    assert connector is not None
    assert connector["argv"] == ["echo", "mock"]
    assert store.get_config("default_connector") == "mockagent"

    # Test connect list, show, test
    res = run_cli(tmp_path, "connect", "ai", "list")
    assert "mockagent" in res.stdout
    
    res = run_cli(tmp_path, "connect", "ai", "show", "mockagent")
    assert "mockagent" in res.stdout

    res = run_cli(tmp_path, "connect", "ai", "test", "mockagent")
    data = json.loads(res.stdout)
    assert data["status"] == "ok"
    
    # Test add source
    run_cli(tmp_path, "add", "--text", "Sample study guidelines context.", "--title", "SyllabusDoc")
    sources = store.list_sources()
    assert len(sources) == 1
    assert sources[0].title == "SyllabusDoc"

    # Test due count (initially 0 since no campaign active yet)
    res = run_cli(tmp_path, "due")
    assert "0" in res.stdout

    # Test config set & show
    run_cli(tmp_path, "config", "set", "user.name", "Stan")
    res = run_cli(tmp_path, "config", "show")
    assert "user.name" in res.stdout
    assert "Stan" in res.stdout

    with patch("builtins.input", side_effect=["Fluent enough.", "No deadline."]), patch("dojo.cli._use_json", return_value=False):
        run_cli(tmp_path, "campaign", "create", "Learn Spanish Grammar", "--level", "intermediate")
        
    # Check that campaign was created
    campaigns = store.list_campaigns()
    assert len(campaigns) == 1
    assert campaigns[0].name == "Grounded French Campaign"  # overridden by mock diagnostic response
    
    # Test campaign history
    res = run_cli(tmp_path, "campaign", "history")
    assert "CREATE" in res.stdout

    # Test campaign export (markdown syllabus)
    export_path = tmp_path / "syllabus_export.md"
    run_cli(tmp_path, "campaign", "export", "--format", "markdown", "--output", str(export_path))
    assert export_path.exists()
    assert "# Grounded French Syllabus" in export_path.read_text(encoding="utf-8")


# ==========================================
# Doctor and Install Gate Tests
# ==========================================

def test_dojo_doctor_clean_and_dirty(tmp_path: Path):
    # 1. Clean run on freshly initialized empty directory (JSON output by default)
    res = run_cli(tmp_path, "doctor")
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert data["errors"] == []
    assert res.returncode == 0

    # Human-friendly print verification
    with patch("dojo.cli._use_json", return_value=False):
        res = run_cli(tmp_path, "doctor")
        assert "Repository directory is completely compliant and clean" in res.stdout
        assert res.returncode == 0

    # 3. Dirty run with unexpected file at root
    dirty_file = tmp_path / "unexpected.txt"
    dirty_file.write_text("random file content", encoding="utf-8")
    
    # JSON verification
    res = run_cli(tmp_path, "doctor", check=False)
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["ok"] is False
    assert "Unexpected file at root: unexpected.txt" in data["errors"]

    # Human-readable verification
    with patch("dojo.cli._use_json", return_value=False):
        res = run_cli(tmp_path, "doctor", check=False)
        assert res.returncode == 1
        assert "Dojo Doctor Diagnostics" in res.stdout
        assert "Unexpected file at root: unexpected.txt" in res.stdout
        assert "Dojo Doctor found 1 issues" in res.stdout

    # 4. Clean up dirty file, verify it works again
    dirty_file.unlink()
    res = run_cli(tmp_path, "doctor")
    assert res.returncode == 0


def test_dojo_doctor_validation_errors(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    
    # Invalid markdown in campaigns (missing campaign.md)
    camp_dir = tmp_path / "campaigns" / "camp_invalid"
    camp_dir.mkdir(parents=True, exist_ok=True)
    
    with patch("dojo.cli._use_json", return_value=False):
        res = run_cli(tmp_path, "doctor", check=False)
        assert res.returncode == 1
        assert "Missing required 'campaign.md'" in res.stdout

    # Invalid YAML frontmatter / schema violation in campaign.md
    camp_md = camp_dir / "campaign.md"
    camp_md.write_text("---\nid: different_id\nname: Test\n---\nSyllabus outline", encoding="utf-8")
    with patch("dojo.cli._use_json", return_value=False):
        res = run_cli(tmp_path, "doctor", check=False)
        assert res.returncode == 1
        assert "Invalid campaign file" in res.stdout


def test_dojo_install_safety_gate(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    dirty_file = tmp_path / "unknown_file.txt"
    dirty_file.write_text("something", encoding="utf-8")

    # Trying to install should fail loudly because repository is dirty
    res = run_cli(tmp_path, "install", "hermes", "--dest", str(tmp_path / "hermes_skill"), check=False)
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["ok"] is False
    assert "Dojo repository validation failed" in data["error"]
    assert "Unexpected file at root: unknown_file.txt" in data["errors"]

    with patch("dojo.cli._use_json", return_value=False):
        res = run_cli(tmp_path, "install", "hermes", "--dest", str(tmp_path / "hermes_skill"), check=False)
        assert res.returncode == 1
        assert "Dojo Doctor found issues in your repository" in res.stdout
        assert "To bypass this check, run install with --force" in res.stdout
        assert not (tmp_path / "hermes_skill").exists()

    # Installing with --force should succeed
    with patch("dojo.cli._is_owned_by_dojo", return_value=True):
        res = run_cli(tmp_path, "install", "hermes", "--dest", str(tmp_path / "hermes_skill"), "--force")
        assert res.returncode == 0
        assert (tmp_path / "hermes_skill").exists()
