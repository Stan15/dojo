from typing import Any, Optional, List, Dict
import json
from pydantic import BaseModel, Field

class CandidateDraft(BaseModel):
    prompt: str = Field(
        description="The complete question, checklist, sub-tasks, options, and context. Must be fully self-contained in Markdown. Do NOT use custom keys like 'learner_tasks' or 'tasks' for prompt content."
    )
    answer: Optional[str] = Field(
        default=None,
        description="The expected answer key, solution code, or reference answers (optional/null if diagnostic/reflection)."
    )
    rubric: Optional[str] = Field(
        default=None,
        description="Grading rubric or evaluation criteria to score the response (optional/null)."
    )
    topic_path: str = Field(
        description="The specific topic path from the active topics (e.g. language.french.tef.nclc7.expression_orale.part_a)."
    )
    difficulty: str = Field(
        description="Difficulty level calibrated to the user ('beginner', 'intermediate', 'advanced')."
    )

class ExerciseGenerateResponse(BaseModel):
    thinking: str = Field(
        description="Your internal scratchpad, analysis, and reasoning about the target topic, strategy, and constraints before drafting candidates."
    )
    candidates: List[CandidateDraft] = Field(
        description="List of drafted practice candidates."
    )

class HypothesisEntry(BaseModel):
    key: str = Field(
        description="Stable unique identifier for the hypothesis (e.g., target_all_four_nclc7_with_oral_gap)."
    )
    description: str = Field(
        description="Detailed explanation of the misconception, pattern, style, or goals."
    )
    topic_path: Optional[str] = Field(
        default=None,
        description="Optional topic scope associated with this pattern."
    )

class CalibratedStrategy(BaseModel):
    mode: str = Field(
        description="Strategy mode ('practice' or 'diagnostic')."
    )
    difficulty: str = Field(
        description="Target difficulty level ('beginner', 'intermediate', 'advanced')."
    )
    scaffolding: str = Field(
        description="Level of scaffolding/hints to provide ('high', 'medium', or 'low')."
    )

class CriteriaEntry(BaseModel):
    min_attempts: int = Field(
        description="Minimum attempts required to complete this phase."
    )
    min_accuracy: float = Field(
        description="Minimum accuracy required to complete this phase (between 0.0 and 1.0)."
    )

class AttackPlanPhase(BaseModel):
    phase: int = Field(
        description="Phase index number."
    )
    topics: List[str] = Field(
        description="List of topic paths targeted in this phase."
    )
    criteria: CriteriaEntry = Field(
        description="Completion criteria for the phase."
    )
    focus: Optional[str] = Field(
        default=None,
        description="Target focus instructions for JIT exercise generation (e.g. combining topics, emphasis)."
    )

class JournalEntryPayload(BaseModel):
    action: str = Field(
        description="The consolidation action ('CREATE', 'INSERT_REMEDIATION', 'SKIP_PHASES', 'RE_ORDER', 'CALIBRATE_STRATEGY', 'PIVOT')."
    )
    trigger: str = Field(
        description="The event or condition that triggered this action."
    )
    status: str = Field(
        description="Journal status ('resolved' or 'active')."
    )
    hypothesis: str = Field(
        description="Pedagogical rationale/hypothesis behind the action."
    )

class ProfileConsolidateResponse(BaseModel):
    thinking: str = Field(
        description="Your internal analysis of the user's recent attempts, patterns, and self-stated constraints/deadlines."
    )
    hypotheses: List[HypothesisEntry] = Field(
        description="List of current active learner hypotheses/misconceptions."
    )
    refined_mission: Optional[str] = Field(
        default=None,
        description="Refined campaign mission statement incorporating goals and constraints."
    )
    calibrated_strategy: Optional[CalibratedStrategy] = Field(
        default=None,
        description="Calibrated campaign strategy parameters."
    )
    revised_attack_plan: Optional[List[AttackPlanPhase]] = Field(
        default=None,
        description="Updated list of curriculum phases."
    )
    syllabus_markdown: Optional[str] = Field(
        default=None,
        description="Markdown syllabus (required when active_phase_index is 0 or when restructuring)."
    )
    source_topic_mappings: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Mapping from linked source IDs to lists of topic paths."
    )
    journal_entry: JournalEntryPayload = Field(
        description="Journal entry explaining the changes made."
    )

def get_schema_instruction(task_name: str) -> str:
    if task_name == "exercise.generate":
        schema_json = json.dumps(ExerciseGenerateResponse.model_json_schema(), indent=2)
        return (
            "\n\nSTRICT OUTPUT FORMAT:\n"
            "You MUST return a single valid JSON object adhering strictly to the JSON Schema below.\n"
            "Do NOT include any markdown code block wrappers (like ```json ... ```) or extra conversational text in your final response if possible, but if you do, ensure the JSON is extractable.\n"
            "All fields are mandatory. Use the 'thinking' field for all your internal reasoning, analysis, and pacing considerations.\n\n"
            f"JSON Schema:\n{schema_json}\n"
        )
    elif task_name == "profile.consolidate":
        schema_json = json.dumps(ProfileConsolidateResponse.model_json_schema(), indent=2)
        return (
            "\n\nSTRICT OUTPUT FORMAT:\n"
            "You MUST return a single valid JSON object adhering strictly to the JSON Schema below.\n"
            "Do NOT include any markdown code block wrappers (like ```json ... ```) or extra conversational text in your final response if possible, but if you do, ensure the JSON is extractable.\n"
            "Use the 'thinking' field for all your internal reasoning, analysis of the user's constraints, and attack plan design decisions.\n\n"
            f"JSON Schema:\n{schema_json}\n"
        )
    else:
        raise ValueError(f"Unknown task name: {task_name}")
