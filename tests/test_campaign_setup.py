import json
from unittest.mock import patch
from dojo.api import DojoAPI
from dojo.connectors import CommandConnectorResult
from dojo import db

def test_format_topic_tree():
    api = DojoAPI(":memory:")
    paths = ["git", "git.basics", "git.branching", "python.lists", "python.lists.sorting"]
    tree_str = api.format_topic_tree(paths)

    expected = (
        "- git\n"
        "  - basics\n"
        "  - branching\n"
        "- python\n"
        "  - lists\n"
        "    - sorting"
    )
    assert tree_str == expected

def test_get_all_topic_paths(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)

    # Initialize DB & add mock records with overlapping/distinct topic paths
    db.init_db(db_path)
    with db.connect(db_path) as session:
        # Add Source
        src = db.Source(
            id="src_1",
            title="Title",
            content="Content",
            kind="text"
        )
        session.add(src)

        # 1. Add Exercise
        ex = db.Exercise(
            id="ex_1",
            source_id="src_1",
            topic_path="python.lists",
            prompt="P",
            answer="A",
            rubric="R",
            source_refs="[]"
        )
        session.add(ex)

        # 2. Add Campaign
        camp = db.Campaign(
            id="camp_1",
            name="Git",
            topic_path="git.basics",
            mission="M",
            attack_plan_json="[]",
        )
        session.add(camp)

        # 3. Add Candidate
        cand = db.Candidate(
            id="cand_1",
            source_id="src_1",
            prompt="P",
            answer="A",
            topic_path="docker.basics",
            source_refs="[]"
        )
        session.add(cand)
        session.commit()

    paths = api.get_all_topic_paths()
    assert paths == ["docker.basics", "git.basics", "python.lists"]

def test_create_campaign_lifecycle(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    db.init_db(db_path)

    # 1. Zero-latency skeleton creation
    campaign = api.create_campaign(
        goal="Learn Docker Compose",
        level="intermediate",
        exclusions="production kubernetes",
        feedback="use local dev setup with PostgreSQL"
    )

    assert campaign["campaign_id"].startswith("camp_")
    assert campaign["name"] == "Learning Campaign: Learn Docker Compose"
    assert campaign["topic_path"] == "learn.docker.compose"
    assert campaign["active_phase_index"] == 0
    assert campaign["syllabus_markdown"] is None

    campaign_id = campaign["campaign_id"]

    # 2. Attach source
    res_source = api.add_source(title="Compose Guide", content="YAML defines services.", kind="text")
    source_id = res_source["source_id"]

    api.attach_source_to_campaign(campaign_id, source_id, purpose="Cheat sheet reference")

    # Verify attached in DB
    with db.connect(db_path) as session:
        camp = session.get(db.Campaign, campaign_id)
        config = json.loads(camp.sources_config_json)
        assert len(config) == 1
        assert config[0]["source_id"] == source_id
        assert config[0]["purpose"] == "Cheat sheet reference"

    # 3. Start practice session (triggers JIT diagnostics since phase is 0)
    mock_jit_payload = {
        "title": "Mastering Docker Compose",
        "base_topic": "docker.compose",
        "diagnostic_questions": [
            "What database engine are you using?",
            "Are you targeting production deployments?"
        ]
    }

    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
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

        sess_res = api.start_practice_session(campaign_id=campaign_id)
        session = sess_res["session"]
        session_id = session["id"]
        assert len(session["exercise_ids"]) == 2

        # Verify campaign got updated with new title, base_topic and plan
        with db.connect(db_path) as db_sess:
            camp = db_sess.get(db.Campaign, campaign_id)
            assert camp.name == "Mastering Docker Compose"
            assert camp.topic_path == "docker.compose"
            plan = json.loads(camp.attack_plan_json)
            assert plan[0]["topics"] == ["docker.compose.diagnostic"]

        # Reveal first onboarding prompt
        prompt_res = api.reveal_prompt(session_id=session_id)
        assert prompt_res["prompt"] == "What database engine are you using?"

        # Submit first answer
        api.submit_answer("PostgreSQL", session_id=session_id)

        # Reveal second onboarding prompt
        prompt_res = api.reveal_prompt(session_id=session_id)
        assert prompt_res["prompt"] == "Are you targeting production deployments?"

        # Submit second answer
        api.submit_answer("No, local dev only.", session_id=session_id)

    # 4. Trigger profile consolidation
    mock_consolidate_payload = {
        "refined_mission": "Focus on local dev Docker Compose environments using PostgreSQL.",
        "calibrated_strategy": {
            "mode": "practice",
            "difficulty": "intermediate",
            "scaffolding": "medium"
        },
        "syllabus_markdown": "# Mastering Docker Compose Syllabus\n\n1. YAML Syntax\n2. Services & Containers",
        "attack_plan": [
            {
                "phase": 0,
                "topics": ["docker.compose.diagnostic"],
                "criteria": {"min_attempts": 2, "min_accuracy": 0.0}
            },
            {
                "phase": 1,
                "topics": ["docker.compose.yaml"],
                "criteria": {"min_attempts": 3, "min_accuracy": 0.8}
            }
        ],
        "source_topic_mappings": {
            source_id: ["docker.compose.yaml"]
        },
        "hypotheses": [
            {"key": "preference.postgres", "description": "Learner wants PostgreSQL as the default database."}
        ],
        "journal_entry": {
            "action": "CREATE",
            "trigger": "Diagnostic consolidation",
            "hypothesis": "Learner has intermediate background but needs YAML basics",
            "status": "resolved"
        }
    }

    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
            status="ok",
            connector_name="mock-agent",
            input_mode="stdin-prompt",
            output_mode="stdout-json-or-text",
            request={},
            raw_stdout=json.dumps(mock_consolidate_payload),
            raw_stderr="",
            stderr_tail="",
            exit_code=0,
            duration_seconds=0.1,
            parse_status="json",
            parsed_stdout=mock_consolidate_payload
        )

        consolidate_res = api.consolidate_learner_profile(campaign_id=campaign_id)
        assert consolidate_res["status"] == "ok"

        # Verify campaign got advanced to Phase 1 and strategy, syllabus, and source config are updated
        with db.connect(db_path) as db_sess:
            camp = db_sess.get(db.Campaign, campaign_id)
            assert camp.active_phase_index == 1
            assert camp.mission == "Focus on local dev Docker Compose environments using PostgreSQL."
            assert camp.syllabus_markdown == "# Mastering Docker Compose Syllabus\n\n1. YAML Syntax\n2. Services & Containers"

            config = json.loads(camp.sources_config_json)
            assert config[0]["topics"] == ["docker.compose.yaml"]


def test_campaign_cli_create_and_link(tmp_path):
    from helpers import run_cli
    db_path = tmp_path / "dojo.sqlite3"
    db.init_db(db_path)

    # Create campaign in JSON mode (zero-latency skeleton)
    out_create = run_cli(
        tmp_path,
        "--db", str(db_path),
        "--json",
        "campaign", "create", "Learn Docker Compose",
        "--level", "intermediate",
        "--feedback", "PostgreSQL"
    ).stdout

    res_create = json.loads(out_create)
    assert res_create["ok"] is True
    assert res_create["type"] == "campaign_created"

    campaign_id = res_create["data"]["campaign_id"]

    # Ingest a source to link
    source_res = run_cli(
        tmp_path,
        "--db", str(db_path),
        "--json",
        "add", "--text", "services: web:", "--title", "compose_cheat_sheet"
    ).stdout

    source_id = json.loads(source_res)["source_id"]

    # Mock connector return for linkage consolidation
    mock_consolidate_payload = {
        "syllabus_markdown": "# Docker Syllabus",
        "attack_plan": [],
        "source_topic_mappings": {
            source_id: ["docker.compose"]
        },
        "hypotheses": []
    }

    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
            status="ok",
            connector_name="mock-agent",
            input_mode="stdin-prompt",
            output_mode="stdout-json-or-text",
            request={},
            raw_stdout=json.dumps(mock_consolidate_payload),
            raw_stderr="",
            stderr_tail="",
            exit_code=0,
            duration_seconds=0.1,
            parse_status="json",
            parsed_stdout=mock_consolidate_payload
        )

        # Test campaign link command
        out_link = run_cli(
            tmp_path,
            "--db", str(db_path),
            "--json",
            "campaign", "link", campaign_id, source_id,
            "--purpose", "compose cheat sheet"
        ).stdout

        res_link = json.loads(out_link)
        assert res_link["ok"] is True
        assert res_link["type"] == "campaign_linked"

        # Verify call context contains expected task key
        assert mock_invoke.call_count == 1
        req = mock_invoke.call_args[0][1]
        assert req["task"] == "profile.consolidate"


def test_campaign_phase_progression(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    db.init_db(db_path)

    # 1. Create a campaign manually
    attack_plan = [
        {
            "phase": 0,
            "topics": ["git.basics"],
            "criteria": {"min_attempts": 2, "min_accuracy": 0.75}
        },
        {
            "phase": 1,
            "topics": ["git.rebase"],
            "criteria": {"min_attempts": 3, "min_accuracy": 0.8}
        }
    ]

    with db.connect(db_path) as session:
        src = db.Source(id="src_1", title="Title", content="Content", kind="syllabus")
        session.add(src)
        camp = db.Campaign(
            id="camp_1",
            name="Git Campaign",
            source_id="src_1",
            topic_path="git",
            mission="Mission",
            attack_plan_json=json.dumps(attack_plan),
            pedagogical_journal_json=json.dumps([
                {
                    "action": "CREATE",
                    "timestamp": "2026-06-15T21:00:00Z",
                    "plan_snapshot": attack_plan
                }
            ]),
            active_phase_index=0
        )
        session.add(camp)

        # Add Exercise
        ex1 = db.Exercise(id="ex_1", source_id="src_1", topic_path="git.basics", prompt="P1", source_refs="[]")
        ex2 = db.Exercise(id="ex_2", source_id="src_1", topic_path="git.basics.commits", prompt="P2", source_refs="[]")
        session.add(ex1)
        session.add(ex2)
        session.commit()

        # Add 2 attempts (score 1.0)
        att1 = db.Attempt(id="att_1", exercise_id="ex_1", source_id="src_1", prompt="P1", user_answer="A1", score=1.0, latency_seconds=2.0, campaign_id="camp_1", consolidated=False)
        att2 = db.Attempt(id="att_2", exercise_id="ex_2", source_id="src_1", prompt="P2", user_answer="A2", score=1.0, latency_seconds=3.0, campaign_id="camp_1", consolidated=False)
        session.add(att1)
        session.add(att2)
        session.commit()

    # Consolidate - mock connector to just return no modifications
    mock_payload = {"hypotheses": []}
    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
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

        api.consolidate_learner_profile(campaign_id="camp_1")

        with db.connect(db_path) as session:
            updated_camp = session.get(db.Campaign, "camp_1")
            assert updated_camp.active_phase_index == 1
            journal = json.loads(updated_camp.pedagogical_journal_json)
            assert len(journal) == 2
            assert journal[1]["action"] == "PHASE_ADVANCE"
            assert journal[1]["performance_snapshot"]["attempts"] == 2
            assert journal[1]["performance_snapshot"]["accuracy"] == 1.0


def test_consolidation_payload_optimizations_and_revisions(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    db.init_db(db_path)

    attack_plan = [
        {
            "phase": 0,
            "topics": ["git.basics"],
            "criteria": {"min_attempts": 2, "min_accuracy": 0.75}
        },
        {
            "phase": 1,
            "topics": ["git.rebase"],
            "criteria": {"min_attempts": 3, "min_accuracy": 0.8}
        }
    ]

    journal = [
        {
            "action": "CREATE",
            "timestamp": "2026-06-15T21:00:00Z",
            "plan_snapshot": attack_plan
        },
        {
            "action": "INSERT_REMEDIATION",
            "timestamp": "2026-06-15T21:10:00Z",
            "status": "active",
            "plan_snapshot": attack_plan,
            "performance_snapshot": {"attempts": 1, "accuracy": 0.0}
        },
        {
            "action": "RESOLVE_REMEDIATION",
            "timestamp": "2026-06-15T21:20:00Z",
            "status": "resolved",
            "plan_snapshot": attack_plan,
            "performance_snapshot": {"attempts": 1, "accuracy": 1.0}
        }
    ]

    with db.connect(db_path) as session:
        src = db.Source(id="src_1", title="Title", content="Content", kind="syllabus")
        session.add(src)
        camp = db.Campaign(
            id="camp_1",
            name="Git Campaign",
            source_id="src_1",
            topic_path="git",
            mission="Mission",
            attack_plan_json=json.dumps(attack_plan),
            pedagogical_journal_json=json.dumps(journal),
            active_phase_index=1
        )
        session.add(camp)

        # Add one attempt to trigger consolidation
        ex = db.Exercise(id="ex_1", source_id="src_1", topic_path="git.rebase", prompt="P1", source_refs="[]")
        session.add(ex)
        session.commit()

        att = db.Attempt(id="att_1", exercise_id="ex_1", source_id="src_1", prompt="P1", user_answer="A1", score=1.0, latency_seconds=2.0, campaign_id="camp_1", consolidated=False)
        session.add(att)
        session.commit()

    # Mock LLM to return a revised attack plan and a new journal entry
    new_attack_plan = [
        {
            "phase": 0,
            "topics": ["git.basics"],
            "criteria": {"min_attempts": 2, "min_accuracy": 0.75}
        },
        {
            "phase": 1,
            "topics": ["git.rebase"],
            "criteria": {"min_attempts": 3, "min_accuracy": 0.8}
        },
        {
            "phase": 2,
            "topics": ["git.advanced_topics"],
            "criteria": {"min_attempts": 2, "min_accuracy": 0.8}
        }
    ]
    mock_payload = {
        "hypotheses": [],
        "revised_attack_plan": new_attack_plan,
        "journal_entry": {
            "action": "PIVOT",
            "trigger": "User completed basic track exceptionally fast",
            "hypothesis": "User is ready for advanced tasks",
            "status": "resolved"
        }
    }

    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
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

        api.consolidate_learner_profile(campaign_id="camp_1")

        # Assertions on the request sent to the LLM (optimizations)
        assert mock_invoke.call_count == 1
        req = mock_invoke.call_args[0][1]
        req_campaign = req["campaign"]

        # 1. Pruning completed phases
        current_plan_in_req = req_campaign["current_attack_plan"]
        assert current_plan_in_req[0]["status"] == "completed"
        assert "criteria" not in current_plan_in_req[0]

        # 2. original/baseline anchor extracted
        assert req_campaign["latest_baseline_plan"] == attack_plan

        # 3. stripping resolved detour snapshots from journal in request
        journal_in_req = req_campaign["pedagogical_journal"]
        assert "plan_snapshot" in journal_in_req[1]
        assert "performance_snapshot" in journal_in_req[1]
        assert "plan_snapshot" not in journal_in_req[2]
        assert "performance_snapshot" not in journal_in_req[2]

        # Assertions on database updates
        with db.connect(db_path) as session:
            updated_camp = session.get(db.Campaign, "camp_1")
            assert json.loads(updated_camp.attack_plan_json) == new_attack_plan

            updated_journal = json.loads(updated_camp.pedagogical_journal_json)
            assert len(updated_journal) == 4
            assert updated_journal[3]["action"] == "PIVOT"
            assert updated_journal[3]["plan_snapshot"] == new_attack_plan


def test_campaign_cli_history(tmp_path):
    from helpers import run_cli
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    db.init_db(db_path)

    # 1. Create a campaign and log some custom entries in pedagogical journal
    attack_plan = [
        {
            "phase": 0,
            "topics": ["git.basics"],
            "criteria": {"min_attempts": 2, "min_accuracy": 0.75}
        }
    ]
    journal = [
        {
            "action": "CREATE",
            "timestamp": "2026-06-15T21:00:00Z",
            "plan_snapshot": attack_plan,
            "trigger": "Initial setup",
            "hypothesis": "Start from basics",
            "active_phase_index": 0
        },
        {
            "action": "PHASE_ADVANCE",
            "timestamp": "2026-06-15T21:10:00Z",
            "plan_snapshot": attack_plan,
            "trigger": "Passed criteria",
            "hypothesis": "Advance",
            "active_phase_index": 0
        }
    ]

    with db.connect(db_path) as session:
        src = db.Source(id="src_1", title="Title", content="Content", kind="syllabus")
        session.add(src)
        camp = db.Campaign(
            id="camp_1",
            name="Git Campaign",
            source_id="src_1",
            topic_path="git",
            mission="Mission",
            attack_plan_json=json.dumps(attack_plan),
            pedagogical_journal_json=json.dumps(journal),
            active_phase_index=0
        )
        session.add(camp)
        session.commit()

    # 2. Run CLI command for campaign history (text mode)
    with patch("dojo.cli._use_json", return_value=False):
        res_text = run_cli(tmp_path, "campaign", "history", "--campaign", "camp_1")
    assert "Pedagogical Journal for Campaign: Git Campaign" in res_text.stdout
    assert "Action: CREATE" in res_text.stdout
    assert "Action: PHASE_ADVANCE" in res_text.stdout
    assert "Trigger: Initial setup" in res_text.stdout

    # 3. Run CLI command for campaign history (json mode)
    res_json = run_cli(tmp_path, "--json", "campaign", "history", "--campaign", "camp_1")
    data = json.loads(res_json.stdout)
    assert data["ok"] is True
    assert data["type"] == "campaign_history"
    assert data["data"]["campaign_id"] == "camp_1"
    assert len(data["data"]["journal"]) == 2

    # 4. Run CLI command with --show-snapshots
    with patch("dojo.cli._use_json", return_value=False):
        res_snapshots = run_cli(tmp_path, "campaign", "history", "--campaign", "camp_1", "--show-snapshots")
    assert "Plan Snapshot:" in res_snapshots.stdout
    assert "Phase 0: topics=[git.basics]" in res_snapshots.stdout


def test_exercise_generate_with_strategy(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    api = DojoAPI(db_path)
    db.init_db(db_path)

    # 1. Setup a campaign with a custom strategy profile
    strategy = {
        "mode": "practice",
        "difficulty": "advanced",
        "scaffolding": "low"
    }
    with db.connect(db_path) as session:
        src = db.Source(id="src_1", title="Title", content="Content of the source", kind="syllabus")
        session.add(src)

        # Add Campaign
        camp = db.Campaign(
            id="camp_1",
            name="Advanced Git",
            source_id="src_1",
            topic_path="git.advanced",
            mission="Master Git",
            attack_plan_json="[]",
            strategy_profile_json=json.dumps(strategy),
        )
        session.add(camp)
        session.commit()

    mock_response = {
        "candidates": [
            {
                "prompt": "Advanced git prompt",
                "answer": "git checkout -b",
                "topic_path": "git.advanced.branch",
                "source_refs": [
                    {
                        "source_id": "src_1",
                        "span": {
                            "start_line": 1,
                            "end_line": 5,
                            "anchor_text": "Content"
                        }
                    }
                ]
            }
        ]
    }

    with patch("dojo.connectors.invoke_command_connector") as mock_invoke:
        mock_invoke.return_value = CommandConnectorResult(
            status="ok",
            connector_name="mock-agent",
            input_mode="stdin-prompt",
            output_mode="stdout-json-or-text",
            request={},
            raw_stdout=json.dumps(mock_response),
            raw_stderr="",
            stderr_tail="",
            exit_code=0,
            duration_seconds=0.1,
            parse_status="json",
            parsed_stdout=mock_response
        )

        # This will trigger JIT candidate generation for topic "git.advanced"
        api.start_practice_session(topic="git.advanced", limit=5)

        # Assertions on the connector call payload
        assert mock_invoke.call_count == 1
        req = mock_invoke.call_args[0][1]
        assert req["task"] == "exercise.generate"

        # Verify strategy profile parameters are in payload
        assert req["strategy_profile"] == strategy

        # Verify that instructions are extended with low scaffolding and advanced difficulty rules
        instructions = req["instructions"]
        assert "Avoid hints, extra context, or explanatory setup; keep the prompt direct and challenging." in instructions
        assert "Target complex, high-level combined applications or edge cases." in instructions


def test_campaign_creation_cancellation(tmp_path):
    import pytest
    from dojo.cli import cmd_campaign_create
    import argparse

    db_path = tmp_path / "dojo.sqlite3"
    db.init_db(db_path)

    args = argparse.Namespace(
        db=str(db_path),
        goal="Learn Algebra",
        level="beginner",
        name=None,
        exclude=None,
        feedback=None,
        json=False
    )

    # Patch start_practice_session to raise KeyboardInterrupt, simulating Ctrl+C mid-run
    # Patch _use_json to return False to simulate interactive TTY mode (otherwise test stdout is captured and defaults to JSON mode)
    with patch("dojo.cli._use_json", return_value=False):
        with patch("dojo.api.DojoAPI.start_practice_session", side_effect=KeyboardInterrupt):
            with pytest.raises(SystemExit) as exc_info:
                cmd_campaign_create(args)

            assert exc_info.value.code == 1

    # Verify that the campaign table is completely empty (rolled back)
    with db.connect(db_path) as session:
        campaigns = session.exec(db.select(db.Campaign)).all()
        assert len(campaigns) == 0
