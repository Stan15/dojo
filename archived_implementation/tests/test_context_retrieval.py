import json
from unittest.mock import patch
from dojo import db
from dojo.api import DojoAPI
from dojo.connectors import CommandConnectorResult
from dojo.generate import (
    parse_markdown_headings,
    score_heading,
    expand_window,
    resolve_paragraph_window,
    resolve_source_context,
)

def test_parse_markdown_headings():
    content = (
        "# Root Heading\n"
        "Some root text.\n"
        "## Sub Heading A\n"
        "Text under A.\n"
        "### Sub Sub A1\n"
        "A1 detail.\n"
        "## Sub Heading B\n"
        "Text under B.\n"
    )
    
    headings = parse_markdown_headings(content)
    assert len(headings) == 4
    
    # Root Heading
    assert headings[0]["title"] == "Root Heading"
    assert headings[0]["level"] == 1
    assert headings[0]["start_line"] == 1
    assert headings[0]["end_line"] == 8
    assert headings[0]["heading_path"] == ["Root Heading"]
    
    # Sub Heading A
    assert headings[1]["title"] == "Sub Heading A"
    assert headings[1]["level"] == 2
    assert headings[1]["start_line"] == 3
    assert headings[1]["end_line"] == 6
    assert headings[1]["heading_path"] == ["Root Heading", "Sub Heading A"]
    
    # Sub Sub A1
    assert headings[2]["title"] == "Sub Sub A1"
    assert headings[2]["level"] == 3
    assert headings[2]["start_line"] == 5
    assert headings[2]["end_line"] == 6
    assert headings[2]["heading_path"] == ["Root Heading", "Sub Heading A", "Sub Sub A1"]
    
    # Sub Heading B
    assert headings[3]["title"] == "Sub Heading B"
    assert headings[3]["level"] == 2
    assert headings[3]["start_line"] == 7
    assert headings[3]["end_line"] == 8
    assert headings[3]["heading_path"] == ["Root Heading", "Sub Heading B"]


def test_score_heading():
    path = ["Docker Guide", "Docker Compose", "Services"]
    
    # Exact match for last component
    s1 = score_heading(path, "docker.compose.services")
    # Docker (idx 0, wt 1) -> +1
    # Compose (idx 1, wt 2) -> +2
    # Services (idx 2, wt 4) -> +4
    # Leaf match "Services" -> +8
    # Total: 15.0
    assert s1 == 15.0
    
    # Disambiguation check
    path2 = ["Windows Setup", "Services"]
    s2 = score_heading(path2, "docker.compose.services")
    # Services (idx 2, wt 4) -> +4
    # Leaf match "Services" -> +8
    # Total: 12.0
    assert s2 == 12.0
    assert s1 > s2
    
    # Parent namespace only
    s3 = score_heading(path, "docker.compose.volumes")
    # Docker -> +1
    # Compose -> +2
    # Leaf match bonus -> 0
    # Total: 3.0
    assert s3 == 3.0


def test_expand_window():
    headings = [
        {"idx": 0, "title": "Root", "level": 1, "start_line": 1, "end_line": 200, "heading_path": ["Root"]},
        {"idx": 1, "title": "Sub A", "level": 2, "start_line": 10, "end_line": 50, "heading_path": ["Root", "Sub A"]},
        {"idx": 2, "title": "Detail A1", "level": 3, "start_line": 20, "end_line": 30, "heading_path": ["Root", "Sub A", "Detail A1"]},
    ]
    
    # If the window is already large enough
    s, e = expand_window(headings, matched_idx=1, total_lines=200, min_lines=30)
    assert s == 10
    assert e == 50
    
    # If Detail A1 is matched (11 lines), min_lines is 30, expands to Sub A (41 lines)
    s, e = expand_window(headings, matched_idx=2, total_lines=200, min_lines=30)
    assert s == 10
    assert e == 50
    
    # If Detail A1 is matched, min_lines is 100, expands to Root (200 lines)
    s, e = expand_window(headings, matched_idx=2, total_lines=200, min_lines=100)
    assert s == 1
    assert e == 200


def test_resolve_paragraph_window():
    content = (
        "Para 1 is about python basics.\n\n"
        "Para 2 details python lists and lists sorting.\n\n"
        "Para 3 details python dicts.\n\n"
        "Para 4 details python tuples.\n\n"
    )
    
    s, e = resolve_paragraph_window(content, "python.lists", min_lines=2)
    # Paragraph 2 matches python and lists
    # Para 2 starts at line 3, ends at line 4
    # With min_lines = 2, Para 2 (lines 3 to 4) is sufficient.
    assert s == 3
    assert e == 4


def test_resolve_source_context():
    content = (
        "# Python Guide\n"
        "Intro text.\n"
        "## Lists\n"
        "Lists are ordered arrays.\n"
        "We can sort lists.\n"
        "## Dicts\n"
        "Dicts are key-value mappings.\n"
    )
    
    # Heading match
    sliced, start, end = resolve_source_context(content, "Python", "python.lists", min_lines=2)
    assert start == 3
    assert end == 5
    assert sliced == "## Lists\nLists are ordered arrays.\nWe can sort lists."
    
    # Plain text paragraph fallback (no headings match)
    plain_content = (
        "Paragraph 1 is about quaternions.\n\n"
        "Paragraph 2 is about rotation matrices.\n\n"
        "Paragraph 3 is about Euler angles.\n"
    )
    sliced, start, end = resolve_source_context(plain_content, "Plain", "math.quaternions", min_lines=1)
    assert start == 1
    assert end == 2
    assert sliced.strip() == "Paragraph 1 is about quaternions."


def test_api_jit_generation_sliced_refs(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    db.init_db(db_path)
    api = DojoAPI(db_path)
    
    # Add Source
    source_content = (
        "# Python Guide\n"
        "Intro text.\n"
        "## Lists\n"
        "Lists are ordered arrays.\n"
        "We can sort lists.\n"
        + "\n".join(f"Lists padding line {i}" for i in range(120)) + "\n"
        "## Dicts\n"
        "Dicts are key-value mappings.\n"
        + "\n".join(f"Dicts padding line {i}" for i in range(120)) + "\n"
    )
    res_src = api.add_source(title="Python Doc", content=source_content, kind="text")
    source_id = res_src["source_id"]
    
    # Create campaign and link source
    camp = api.create_campaign(goal="Learn Python Lists")
    camp_id = camp["campaign_id"]
    api.attach_source_to_campaign(camp_id, source_id, purpose="Cheat sheet reference")
    
    # Manually configure campaign phase and target topic
    with db.connect(db_path) as session:
        c = session.get(db.Campaign, camp_id)
        # Advance campaign to practice phase 1
        c.active_phase_index = 1
        c.topic_path = "python.lists"
        c.strategy_profile_json = json.dumps({"mode": "practice", "difficulty": "intermediate", "scaffolding": "medium"})
        # Set topics mapped in config
        c.sources_config_json = json.dumps([{
            "source_id": source_id,
            "purpose": "Lists",
            "topics": ["python.lists"]
        }])
        c.attack_plan_json = json.dumps([
            {"phase": 0, "topics": ["python.lists.diagnostic"]},
            {"phase": 1, "topics": ["python.lists"], "criteria": {"min_attempts": 3, "min_accuracy": 0.8}}
        ])
        session.add(c)
        session.commit()
        
    mock_exercise_payload = {
        "candidates": [
            {
                "prompt": "How do you append to a list?",
                "answer": "Use list.append()",
                "topic_path": "python.lists",
                "source_refs": [{
                    "source_id": source_id,
                    "span": {
                        "start_line": 3,
                        "end_line": 4,
                        "anchor_text": "Python Doc"
                    }
                }]
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
            raw_stdout=json.dumps(mock_exercise_payload),
            raw_stderr="",
            stderr_tail="",
            exit_code=0,
            duration_seconds=0.1,
            parse_status="json",
            parsed_stdout=mock_exercise_payload
        )
        
        # Trigger practice session (re-queried after diagnostic onboarding)
        sess_res = api.start_practice_session(campaign_id=camp_id, reset=True)
        
        # Assert JIT resolve_source_context was called and only passed the lists heading span
        called_request = mock_invoke.call_args[0][1]
        assert called_request["task"] == "exercise.generate"
        source_data = called_request["source"]
        
        # Verify content was sliced correctly
        assert "## Lists" in source_data["content"]
        assert "## Dicts" not in source_data["content"]
        
        # Verify source_refs span in request was set to sliced line range [3, 5]
        ref = source_data["refs"][0]
        assert ref["source_id"] == source_id
        assert ref["span"]["start_line"] == 3
        assert ref["span"]["end_line"] == 125


def test_locator_tracking_in_db(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    db.init_db(db_path)
    api = DojoAPI(db_path)
    
    # 1. Test Ingestion with explicit --locator (representing a YouTube URL)
    output = api.add_source(
        title="Video Transcript",
        content="This is the video transcription.",
        kind="text",
        path="https://youtube.com/watch?v=12345",
    )
    
    source_id = output["source_id"]
    with db.connect(db_path) as session:
        src = session.get(db.Source, source_id)
        assert src.path == "https://youtube.com/watch?v=12345"


def test_cli_source_show_slicing(tmp_path):
    from helpers import run_cli
    db_path = tmp_path / "dojo.sqlite3"
    db.init_db(db_path)
    api = DojoAPI(db_path)
    
    # Ingest a source with multiple lines
    content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    res = api.add_source(title="Multiline", content=content, kind="text")
    source_id = res["source_id"]
    
    # Test dojo source show --start-line 2 --end-line 4 --json
    out = run_cli(tmp_path, "--json", "source", "show", source_id, "--start-line", "2", "--end-line", "4").stdout
    data = json.loads(out)
    assert data["content"] == "Line 2\nLine 3\nLine 4"
    assert data["title"] == "Multiline"
