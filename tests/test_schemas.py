import json
from dojo.schemas import (
    get_schema_instruction,
    ExerciseGenerateResponse,
    ProfileConsolidateResponse,
)
from dojo.generate import _normalize_candidate, validate_exercise_generate_output

def test_schemas_generate_json_schema():
    # Verify that get_schema_instruction generates correct schemas
    gen_instructions = get_schema_instruction("exercise.generate")
    assert "JSON Schema" in gen_instructions
    assert "thinking" in gen_instructions
    assert "candidates" in gen_instructions

    consolidate_instructions = get_schema_instruction("profile.consolidate")
    assert "JSON Schema" in consolidate_instructions
    assert "thinking" in consolidate_instructions
    assert "revised_attack_plan" in consolidate_instructions

def test_normalize_candidate_stiches_lists():
    # Verify that when candidate dict contains extra structural keys,
    # they are appended as formatted Markdown lists to the returned candidate prompt.
    raw_candidate = {
        "prompt": "Complete the task.",
        "topic_path": "test.topic",
        "difficulty": "intermediate",
        "answer": "Answer key",
        "learner_tasks": [
            "Write a checklist item",
            {"task": "Detail task", "description": "Do this"}
        ],
        "scaffolding": {
            "hints": ["First hint", "Second hint"]
        }
    }

    normalized, err = _normalize_candidate(raw_candidate)
    assert err is None
    assert normalized is not None
    assert "Complete the task." in normalized["prompt"]
    assert "Learner Tasks:" in normalized["prompt"]
    assert "Write a checklist item" in normalized["prompt"]
    assert "Detail task" in normalized["prompt"]
    assert "Do this" in normalized["prompt"]
    assert "Scaffolding" in normalized["prompt"]
    assert "First hint" in normalized["prompt"]

def test_validate_exercise_generate_output_with_response_wrapper():
    # Verify that validate_exercise_generate_output accepts a response object
    # wrapped in ExerciseGenerateResponse schema
    raw_payload = {
        "thinking": "We need to generate exercises.",
        "topic_span": {
            "existing_topic": "test.topic",
            "active_topics_covered": ["test.topic"],
            "mission_alignment": "Aligns with testing",
            "note": None
        },
        "exercise_draft": {
            "set_title": "Python Basics",
            "target_outcome": "Demonstrate python printing",
            "candidates": [
                {
                    "prompt": "Write a python script.",
                    "topic_path": "test.topic",
                    "difficulty": "intermediate",
                    "answer": "print('hello')",
                    "rubric": "Code should print hello."
                }
            ]
        }
    }

    val = validate_exercise_generate_output(raw_payload)
    assert val["ok"] is True
    assert len(val["candidates"]) == 1
    assert val["candidates"][0]["prompt"] == "Write a python script."
    assert val["candidates"][0]["answer"] == "print('hello')"

def test_profile_consolidate_response_validation():
    # Verify that ProfileConsolidateResponse can validate a complete JSON payload
    raw_consolidate = {
        "thinking": "Analyzing attempts.",
        "hypotheses": [
            {
                "key": "test_hyp",
                "description": "User makes typo mistakes.",
                "topic_path": "test.topic"
            }
        ],
        "refined_mission": "New mission",
        "calibrated_strategy": {
            "mode": "practice",
            "difficulty": "intermediate",
            "scaffolding": "high"
        },
        "revised_attack_plan": [
            {
                "phase": 1,
                "topics": ["test.topic"],
                "criteria": {
                    "min_attempts": 5,
                    "min_accuracy": 0.8
                },
                "focus": "Focus on formatting"
            }
        ],
        "journal_entry": {
            "action": "CREATE",
            "trigger": "Init",
            "status": "resolved",
            "hypothesis": "Test hypothesis"
        }
    }

    # This should validate cleanly
    validated = ProfileConsolidateResponse.model_validate(raw_consolidate)
    assert validated.thinking == "Analyzing attempts."
    assert validated.hypotheses[0].key == "test_hyp"
    assert validated.revised_attack_plan[0].criteria.min_attempts == 5
    assert validated.journal_entry.action == "CREATE"


def test_prompt_loader_interpolation():
    from dojo.prompts import load_prompt
    placeholders = {
        "active_topics_context": "Active topic context",
        "phase_focus_context": "Phase focus context",
        "learner_profile_context": "Learner profile context",
        "schema_instructions": '{"type": "object", "properties": {"thinking": {"type": "string"}}}'
    }
    result = load_prompt("exercise_generate.md", placeholders)
    assert "Active topic context" in result
    assert "Phase focus context" in result
    assert "Learner profile context" in result
    assert '{"type": "object"' in result


def test_prompt_loader_signature_verification():
    import warnings
    from dojo.prompts import load_prompt

    placeholders = {
        "active_topics_context": "Active topic context",
        "phase_focus_context": "Phase focus context",
    }
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        load_prompt("exercise_generate.md", placeholders)
        assert len(w) >= 1
        assert any("remaining un-interpolated placeholders" in str(warn.message) for warn in w)


def test_schemas_pydantic_validation():
    from dojo.schemas import ExerciseGenerateResponse
    valid_data = {
        "thinking": "Valid reasoning",
        "topic_span": {
            "existing_topic": "math.arithmetic",
            "active_topics_covered": ["math.arithmetic"],
            "mission_alignment": "Practices basic addition"
        },
        "exercise_draft": {
            "set_title": "Addition practice",
            "target_outcome": "Fluency in simple addition",
            "candidates": [
                {
                    "prompt": "Evaluate 2 + 2",
                    "answer": "4",
                    "topic_path": "math.arithmetic",
                    "source_refs": [],
                    "difficulty": "intermediate"
                }
            ]
        }
    }
    resp = ExerciseGenerateResponse.model_validate(valid_data)
    assert resp.thinking == "Valid reasoning"
    assert resp.topic_span.existing_topic == "math.arithmetic"
    assert resp.exercise_draft.set_title == "Addition practice"
    assert len(resp.exercise_draft.candidates) == 1
