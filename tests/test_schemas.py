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
