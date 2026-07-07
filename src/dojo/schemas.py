from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ==========================================
# Shared plan structures
# ==========================================

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



# ==========================================
# Task Result Schemas (v1 task contract, ADR 010)
#
# What a fulfiller submits for each task kind. Validation here is the I5
# boundary: every numeric limit mirrors src/dojo/limits.py, and tests assert
# prompts and these gates never drift. Purely mechanical cross-checks that need
# store state (evidence ⊆ answer, route target exists, exact item count) live
# in the appliers.
# ==========================================

from . import limits as _limits
from typing import Literal
from pydantic import field_validator


def _cap_words(field_name: str, cap: int):
    def _check(cls, v):
        if v is not None and _limits.word_count(v) > cap:
            raise ValueError(f"{field_name} exceeds {cap} words ({_limits.word_count(v)})")
        return v

    return _check


class GeneratedItem(BaseModel):
    prompt: str = Field(min_length=1)
    answer: Optional[str] = None
    rubric: Optional[str] = None
    skill: Literal["recall", "explain", "apply", "produce", "critique", "diagnostic"]

    _cap_prompt = field_validator("prompt")(
        _cap_words("prompt", _limits.GENERATE_PROMPT_WORDS)
    )
    _cap_answer = field_validator("answer")(
        _cap_words("answer", _limits.GENERATE_ANSWER_WORDS)
    )


class GenerateResult(BaseModel):
    items: List[GeneratedItem] = Field(min_length=1, max_length=_limits.GENERATE_MAX_ITEMS)
    note: Optional[str] = None

    _cap_note = field_validator("note")(_cap_words("note", _limits.GENERATE_NOTE_WORDS))


class GradeResult(BaseModel):
    score: float
    evidence: str = Field(min_length=1)
    feedback: str = Field(min_length=1)
    error_tag: Optional[str] = None

    @field_validator("score")
    @classmethod
    def _score_is_a_band(cls, v: float) -> float:
        if v not in _limits.GRADE_BANDS:
            raise ValueError(f"score must be one of {_limits.GRADE_BANDS}, got {v}")
        return v

    _cap_evidence = field_validator("evidence")(
        _cap_words("evidence", _limits.GRADE_EVIDENCE_WORDS)
    )
    _cap_feedback = field_validator("feedback")(
        _cap_words("feedback", _limits.GRADE_FEEDBACK_WORDS)
    )
    _cap_error_tag = field_validator("error_tag")(
        _cap_words("error_tag", _limits.GRADE_ERROR_TAG_WORDS)
    )


class InsightUpdate(BaseModel):
    op: Literal["create", "update", "resolve"]
    id: Optional[str] = None  # required for update/resolve; checked below
    key: Optional[str] = None  # required for create: stable dotted label
    text: Optional[str] = None  # required for create/update
    evidence: List[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)

    _cap_text = field_validator("text")(_cap_words("text", _limits.REFLECT_INSIGHT_WORDS))
    _cap_reason = field_validator("reason")(_cap_words("reason", _limits.REFLECT_REASON_WORDS))

    @field_validator("key")
    @classmethod
    def _key_shape(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"[a-z0-9_]+(\.[a-z0-9_]+)*", v):
            raise ValueError("key must be a dotted lowercase label, e.g. conditional.aux_choice")
        return v

    @model_validator(mode="after")
    def _op_requirements(self):
        if self.op in ("update", "resolve") and not self.id:
            raise ValueError(f"op={self.op} requires the existing insight id")
        if self.op in ("create", "update") and not self.text:
            raise ValueError(f"op={self.op} requires text")
        if self.op == "create" and not self.key:
            raise ValueError("op=create requires a key (dotted lowercase label)")
        if self.op == "create" and not self.evidence:
            raise ValueError("op=create requires evidence attempt ids")
        return self


class StrategyChange(BaseModel):
    difficulty: Optional[Literal["beginner", "intermediate", "advanced"]] = None
    scaffolding: Optional[Literal["high", "medium", "low"]] = None
    reason: str = Field(min_length=1)

    _cap_reason = field_validator("reason")(_cap_words("reason", _limits.REFLECT_REASON_WORDS))

    @model_validator(mode="after")
    def _changes_something(self):
        if self.difficulty is None and self.scaffolding is None:
            raise ValueError("strategy change must set difficulty and/or scaffolding")
        return self


class PlanRevision(BaseModel):
    phases: List[AttackPlanPhase] = Field(min_length=1, max_length=_limits.PLAN_MAX_PHASES)
    reason: str = Field(min_length=1)

    _cap_reason = field_validator("reason")(_cap_words("reason", _limits.REFLECT_REASON_WORDS))


class ReflectResult(BaseModel):
    insight_updates: List[InsightUpdate] = Field(default_factory=list)
    strategy: Optional[StrategyChange] = None
    plan_revision: Optional[PlanRevision] = None
    journal: str = Field(min_length=1)

    _cap_journal = field_validator("journal")(
        _cap_words("journal", _limits.REFLECT_JOURNAL_WORDS)
    )

    @model_validator(mode="after")
    def _bounded_creates(self):
        creates = sum(1 for u in self.insight_updates if u.op == "create")
        if creates > _limits.REFLECT_MAX_NEW_INSIGHTS:
            raise ValueError(
                f"at most {_limits.REFLECT_MAX_NEW_INSIGHTS} new insights per run, got {creates}"
            )
        return self


class PlanTopic(BaseModel):
    path: str = Field(min_length=1, pattern=r"^[a-z0-9_]+(\.[a-z0-9_]+)*$")
    kind: Literal["recall", "skill"]
    summary: str = ""

    @field_validator("path")
    @classmethod
    def _depth(cls, v: str) -> str:
        if v.count(".") + 1 > _limits.PLAN_MAX_TOPIC_DEPTH:
            raise ValueError(f"topic path deeper than {_limits.PLAN_MAX_TOPIC_DEPTH} levels: {v}")
        return v


class PlanResult(BaseModel):
    mission: str = Field(min_length=1)
    topics: List[PlanTopic] = Field(min_length=1, max_length=_limits.PLAN_MAX_TOPICS)
    phases: List[AttackPlanPhase] = Field(
        min_length=_limits.PLAN_MIN_PHASES, max_length=_limits.PLAN_MAX_PHASES
    )
    refinement_questions: List[str] = Field(
        default_factory=list, max_length=_limits.PLAN_MAX_QUESTIONS
    )

    _cap_mission = field_validator("mission")(
        _cap_words("mission", _limits.PLAN_MISSION_WORDS)
    )

    @field_validator("refinement_questions")
    @classmethod
    def _cap_questions(cls, v: List[str]) -> List[str]:
        for q in v:
            if _limits.word_count(q) > _limits.PLAN_QUESTION_WORDS:
                raise ValueError(f"refinement question exceeds {_limits.PLAN_QUESTION_WORDS} words: {q!r}")
        return v

    @model_validator(mode="after")
    def _phase_topics_exist(self):
        declared = {t.path for t in self.topics}
        for phase in self.phases:
            for tp in phase.topics:
                if tp not in declared:
                    raise ValueError(f"phase {phase.phase} references undeclared topic: {tp}")
        return self


class RouteResult(BaseModel):
    action: Literal["attach", "new_topic", "propose_campaign", "stay_inbox"]
    campaign: Optional[str] = None
    topic_path: Optional[str] = None
    new_name: Optional[str] = None
    new_mission: Optional[str] = None
    confidence: Literal["high", "low"]
    reason: str = Field(min_length=1)
    seed: bool = False

    _cap_reason = field_validator("reason")(_cap_words("reason", _limits.ROUTE_REASON_WORDS))
    _cap_new_name = field_validator("new_name")(
        _cap_words("new_name", _limits.ROUTE_NEW_NAME_WORDS)
    )
    _cap_new_mission = field_validator("new_mission")(
        _cap_words("new_mission", _limits.ROUTE_NEW_MISSION_WORDS)
    )

    @model_validator(mode="after")
    def _action_requirements(self):
        if self.action == "attach" and not (self.campaign and self.topic_path):
            raise ValueError("attach requires campaign and topic_path")
        if self.action == "new_topic" and not (self.campaign and self.topic_path):
            raise ValueError("new_topic requires campaign and the new topic_path")
        if self.action == "propose_campaign" and not (self.new_name and self.new_mission):
            raise ValueError("propose_campaign requires new_name and new_mission")
        return self


RESULT_SCHEMAS: Dict[str, type[BaseModel]] = {
    "exercise.generate": GenerateResult,
    "exercise.diagnostic": GenerateResult,
    "attempt.grade": GradeResult,
    "campaign.reflect": ReflectResult,
    "campaign.plan": PlanResult,
    "capture.route": RouteResult,
}


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
    feedback: Optional[str] = None  # the learner's own comment (reflection input)
    grader: Optional[str] = None  # "exact" | "self" | "ai" — I10: who produced the score
    grade_feedback: Optional[str] = None  # grader → learner, one correction
    grade_evidence: Optional[str] = None  # verbatim quote from the answer
    error_tag: Optional[str] = None  # compact pattern label, feeds reflection
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
