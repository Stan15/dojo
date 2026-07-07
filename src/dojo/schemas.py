from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ==========================================
# LLM Response Schemas (JIT Gen / Consolidation)
# ==========================================

class CandidateDraft(BaseModel):
    prompt: str = Field(
        description="The complete question, checklist, sub-tasks, options, and context. Must be fully self-contained in Markdown."
    )
    answer: Optional[str] = Field(
        default=None,
        description="The expected answer key, solution code, or reference answers (optional)."
    )
    rubric: Optional[str] = Field(
        default=None,
        description="Grading rubric or evaluation criteria to score the response (optional)."
    )
    topic_path: str = Field(
        description="The specific topic path from the active topics (e.g. language.french.tef.nclc7.expression_orale.part_a)."
    )
    difficulty: str = Field(
        description="Difficulty level calibrated to the user ('beginner', 'intermediate', 'advanced')."
    )


class TopicSpan(BaseModel):
    existing_topic: str = Field(
        description="The parent topic namespace (e.g. language.french.tef.nclc7)."
    )
    active_topics_covered: List[str] = Field(
        description="The specific subtopics from the active topics list covered by the drafted exercises."
    )
    mission_alignment: str = Field(
        description="Text description of how the drafted exercises align with the user's campaign mission."
    )
    note: Optional[str] = Field(
        default=None,
        description="Any generation details, assumptions, or warnings."
    )


class ExerciseDraft(BaseModel):
    set_title: str = Field(
        description="Title describing this JIT practice set."
    )
    target_outcome: str = Field(
        description="Target outcome or objective for this practice set."
    )
    candidates: List[CandidateDraft] = Field(
        description="List of drafted practice candidates."
    )


class ExerciseGenerateResponse(BaseModel):
    thinking: str = Field(
        description="Your internal scratchpad, analysis, and reasoning about the target topic, strategy, and constraints before drafting candidates."
    )
    topic_span: TopicSpan = Field(
        description="The topic scope and mission alignment details."
    )
    exercise_draft: ExerciseDraft = Field(
        description="The exercise drafts containing candidate practice questions."
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


# ==========================================
# File System Entity Schemas (with defaults/omissions)
# ==========================================

class StoredEntity(BaseModel):
    """Base for entities persisted by the Store.

    `extra="allow"`: unknown frontmatter keys a human adds to their files are
    part of the storage contract (ADR 011) — they must survive read-modify-write,
    so entity models carry them through instead of dropping them.

    `_body_field` names the one long-text field serialized as the markdown body.
    Bodies are normalized (leading/trailing whitespace stripped) at construction:
    an editor adding a POSIX final newline must never register as a change.
    """

    model_config = ConfigDict(extra="allow")
    _body_field: ClassVar[Optional[str]] = None

    @model_validator(mode="after")
    def _normalize_body(self):
        bf = type(self)._body_field
        if bf:
            val = getattr(self, bf, None)
            if isinstance(val, str) and val != val.strip():
                setattr(self, bf, val.strip())
        return self


class Source(StoredEntity):
    _body_field: ClassVar[Optional[str]] = "content"

    id: str
    title: str
    kind: str
    path: Optional[str] = None
    mission: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Omitted from frontmatter, maps to the Markdown file body
    content: str = ""


class Campaign(StoredEntity):
    _body_field: ClassVar[Optional[str]] = "syllabus_markdown"

    id: str
    name: str
    source_id: Optional[str] = None
    topic_path: Optional[str] = None
    mission: str
    active_phase_index: int = 0
    strategy_profile: Dict[str, Any] = Field(default_factory=dict)
    sources_config: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "active"
    attack_plan: List[AttackPlanPhase] = Field(default_factory=list)
    pedagogical_journal: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Omitted from frontmatter, maps to the Markdown file body
    syllabus_markdown: str = ""


class Exercise(StoredEntity):
    _body_field: ClassVar[Optional[str]] = "prompt"

    id: str
    topic_path: str
    difficulty: str
    generation_run: Optional[str] = None
    candidate_id: Optional[str] = None
    archived: bool = False
    quality: str = "reviewed"
    answer: Optional[str] = None
    rubric: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Omitted from frontmatter, maps to the Markdown file body
    prompt: str


class Candidate(StoredEntity):
    _body_field: ClassVar[Optional[str]] = "prompt"

    id: str
    topic_path: str
    difficulty: str
    generation_run: Optional[str] = None
    archived: bool = False
    quality: str = "reviewed"
    answer: Optional[str] = None
    rubric: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Omitted from frontmatter, maps to the Markdown file body
    prompt: str


class Attempt(StoredEntity):
    _body_field: ClassVar[Optional[str]] = "user_answer"

    id: str
    session_id: str
    exercise_id: str
    campaign_id: str
    score: float
    latency_seconds: float
    skip_reason: Optional[str] = None
    feedback: Optional[str] = None
    reflected: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    prompt: str = ""  # The prompt at the time of attempt
    # Omitted from frontmatter, maps to the Markdown file body
    user_answer: str = ""


class Insight(StoredEntity):
    _body_field: ClassVar[Optional[str]] = "description"

    id: str
    key: str
    sources: List[str] = Field(default_factory=list)
    generation_run: Optional[str] = None
    status: str = "active"
    topic_path: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Omitted from frontmatter, maps to the Markdown file body
    description: str


class Task(StoredEntity):
    """A pending unit of AI judgment (ADR 010) — the only seam between the
    deterministic core and whatever model fulfills it.

    The compiled prompt is the markdown body, so any fulfiller (harness,
    subprocess connector, future API worker) can be pointed at the file itself
    instead of re-emitting the payload through a conversation.
    """

    _body_field: ClassVar[Optional[str]] = "prompt"

    id: str
    kind: str  # exercise.generate | attempt.grade | campaign.reflect | campaign.plan | capture.route
    status: str = "pending"  # pending | fulfilled | failed
    campaign_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)  # applier inputs (session_id, n_items, …)
    submissions: int = 0
    max_submissions: int = 3  # first try + 2 retries (I5)
    error_history: List[str] = Field(default_factory=list)
    payload_bytes: int = 0
    response_bytes: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Omitted from frontmatter, maps to the Markdown file body
    prompt: str = ""


class PracticeSession(StoredEntity):
    id: str
    status: str = "active"
    exercise_ids: List[str] = Field(default_factory=list)
    current_index: int = 0
    current_attempt_started_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
