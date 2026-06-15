import json

from dojo.generate import ExerciseGenerateRequest, validate_exercise_generate_output


def test_task_request_treats_topic_as_optional_parent_hint():
    req = ExerciseGenerateRequest(
        source_id="src_1",
        source_title="Notes",
        source_refs=[{"source_id": "src_1", "span": "1-20"}],
        topic="science.physics",
    ).to_task_request()
    assert req["task"] == "exercise.generate"
    assert req["version"] == 1
    assert req["topic_hint"] == "science.physics"
    assert "optional parent-topic hint" in req["instructions"]
    assert req["expected_artifacts"] == ["topic_span", "exercise_draft"]


def test_validator_accepts_multi_topic_candidates_and_simple_arrays():
    output = {
        "candidates": [
            {"prompt": "What is velocity?", "answer": "Displacement over time", "topic_path": "science.physics.kinematics", "source_refs": [{"source_id": "src_1", "span": "1-3"}]},
            {"prompt": "What is momentum?", "rubric": {"must": ["mass", "velocity"]}, "topic_path": "science.physics.momentum", "source_ref": {"source_id": "src_1", "span": "7-9"}},
        ]
    }
    result = validate_exercise_generate_output(output)
    assert result["ok"] is True
    assert [c["topic_path"] for c in result["candidates"]] == ["science.physics.kinematics", "science.physics.momentum"]

    simple = json.dumps([
        {"prompt": "Define derivative", "answer": "Instantaneous rate of change", "topic": "math.calculus", "provenance": {"source_id": "src_2", "span": "4-5"}}
    ])
    assert validate_exercise_generate_output(simple)["ok"] is True


def test_validator_reports_malformed_or_incomplete_output():
    malformed = validate_exercise_generate_output("not json")
    assert malformed["ok"] is False
    assert "malformed JSON" in malformed["diagnostics"][0]

    incomplete = validate_exercise_generate_output({"candidates": [{"prompt": "No topic"}]})
    assert incomplete["ok"] is False
    assert "missing required fields" in incomplete["diagnostics"][0]
