"""Every persisted and validated shape in dojo, in one place (ADR 006).

Three families:

- **Plan structures** (`AttackPlanPhase`, `CriteriaEntry`) — shared between
  campaigns and the plan/reflect task results.
- **Task result schemas** (`GenerateResult`, `GradeResult`, `ReflectResult`,
  `PlanResult`, `RouteResult`) — what a fulfiller's JSON must parse into at
  `task submit`. This is the I5 validation boundary: word caps and counts
  mirror `limits.py`, so a weak model physically cannot flood the store.
  `RESULT_SCHEMAS` maps task kind → schema.
- **Stored entities** (`Source`, `Campaign`, `Exercise`, …) — subclasses of
  `StoredEntity`, serialized as markdown files with YAML frontmatter; one
  designated field becomes the file body (ADR 011 public storage contract).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ==========================================
# Shared plan structures
# ==========================================

class CriteriaEntry(BaseModel):
    """Mastery gate for one attack-plan phase; `api` checks it in
    `_evaluate_campaign_phase_advancement` — pure arithmetic, no AI."""

    min_attempts: int = Field(
        description="Minimum attempts required to complete this phase."
    )
    min_accuracy: float = Field(
        description="Minimum accuracy required to complete this phase (between 0.0 and 1.0)."
    )



class AttackPlanPhase(BaseModel):
    """One phase of a campaign's attack plan: which topics are in play and
    the criteria to graduate past it. The plan is data, not prose — reflection
    may revise it (`PlanRevision`) but phase advancement is deterministic."""

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
    """One exercise a generation fulfiller proposes. `skill` classifies the
    cognitive act (recall repeats verbatim under FSRS; the rest are
    disposable, topic-scheduled — ADR 012). Prompt/answer word caps stop
    weak-model rambling at the boundary."""

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


class Intervention(BaseModel):
    """The generator's structured refusal (meta-learning escape hatch): when the
    mission/topic is too vague or context is missing, sharp questions beat bad
    exercises. Questions become diagnostic items in the normal loop."""

    kind: Literal["clarify_goal", "need_context", "scope_too_broad"]
    questions: List[str] = Field(min_length=1, max_length=_limits.INTERVENTION_MAX_QUESTIONS)
    reason: str = Field(min_length=1)

    _cap_reason = field_validator("reason")(
        _cap_words("reason", _limits.INTERVENTION_REASON_WORDS)
    )

    @field_validator("questions")
    @classmethod
    def _cap_question_words(cls, v: List[str]) -> List[str]:
        for q in v:
            if _limits.word_count(q) > _limits.INTERVENTION_QUESTION_WORDS:
                raise ValueError(
                    f"intervention question exceeds {_limits.INTERVENTION_QUESTION_WORDS} words: {q!r}"
                )
        return v


class GenerateResult(BaseModel):
    """Submission shape for `exercise.generate` / `exercise.diagnostic`
    tasks: exercises OR an `Intervention`, never both, never neither."""

    items: List[GeneratedItem] = Field(default_factory=list, max_length=_limits.GENERATE_MAX_ITEMS)
    note: Optional[str] = None
    intervention: Optional[Intervention] = None

    _cap_note = field_validator("note")(_cap_words("note", _limits.GENERATE_NOTE_WORDS))

    @model_validator(mode="after")
    def _items_xor_intervention(self):
        if self.intervention is not None and self.items:
            raise ValueError("return exercises OR an intervention, never both")
        if self.intervention is None and not self.items:
            raise ValueError("no items and no intervention — return one or the other")
        return self


class GradeResult(BaseModel):
    """Submission shape for `attempt.grade`: a banded score (only the values
    in `limits.GRADE_BANDS`), a verbatim `evidence` quote from the learner's
    answer (extract-never-enrich, checked by the applier), one `feedback`
    correction, and an optional error-pattern tag that feeds reflection."""

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
    """One reflection edit to the learner model: create (needs key + text +
    evidence attempt ids), update (id + text), or resolve (id). Evidence
    requirements keep insights grounded in actual attempts, not vibes."""

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
    """Reflection's dial adjustment: difficulty and/or scaffolding (at least
    one), with a reason. These are the ONLY strategy knobs a model can turn."""

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
    """Reflection's replacement attack plan (whole-plan swap, bounded phase
    count). The applier decides its fate by change authority: `evidence`
    cites attempt ids carrying the learner's OWN feedback that asked for the
    change — with it (or for mechanically-minor edits) the revision applies;
    without it, destructive revisions become a proposal awaiting
    `dojo plan confirm`."""

    phases: List[AttackPlanPhase] = Field(min_length=1, max_length=_limits.PLAN_MAX_PHASES)
    evidence: List[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)

    _cap_reason = field_validator("reason")(_cap_words("reason", _limits.REFLECT_REASON_WORDS))


class ReflectResult(BaseModel):
    """Submission shape for `campaign.reflect`: bounded insight edits (new
    creates capped per run), optional strategy change and plan revision, an
    ask-don't-restructure `questions` channel (they become diagnostic items;
    answers are citable evidence for a later revision), and a mandatory
    journal line for the pedagogical record."""

    insight_updates: List[InsightUpdate] = Field(default_factory=list)
    strategy: Optional[StrategyChange] = None
    plan_revision: Optional[PlanRevision] = None
    questions: List[str] = Field(default_factory=list, max_length=_limits.REFLECT_MAX_QUESTIONS)
    journal: str = Field(min_length=1)

    _cap_journal = field_validator("journal")(
        _cap_words("journal", _limits.REFLECT_JOURNAL_WORDS)
    )

    @field_validator("questions")
    @classmethod
    def _cap_question_words(cls, v: List[str]) -> List[str]:
        for q in v:
            if _limits.word_count(q) > _limits.REFLECT_QUESTION_WORDS:
                raise ValueError(
                    f"question exceeds {_limits.REFLECT_QUESTION_WORDS} words: {q!r}"
                )
        return v

    @model_validator(mode="after")
    def _bounded_creates(self):
        creates = sum(1 for u in self.insight_updates if u.op == "create")
        if creates > _limits.REFLECT_MAX_NEW_INSIGHTS:
            raise ValueError(
                f"at most {_limits.REFLECT_MAX_NEW_INSIGHTS} new insights per run, got {creates}"
            )
        return self


class PlanTopic(BaseModel):
    """One topic a plan declares: dot-path (bounded depth), recall/skill
    kind, optional summary. Phases may only reference declared topics."""

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
    """Submission shape for `campaign.plan`: distilled mission, bounded topic
    registry, phased attack plan over those topics only, plus optional
    refinement questions back to the learner."""

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
    """Submission shape for `capture.route`: where a capture should live.
    attach/new_topic need a campaign + topic path; propose_campaign needs a
    name + mission; stay_inbox is an honest "not sure". `seed` asks filing to
    also emit a first generation task from the capture."""

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
    "goal.route": RouteResult,  # same contract; the applier differs (dojo learn)
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
    """Learning material the user trusts (note, article, book excerpt…),
    stored verbatim at `sources/<id>.md` with the content as the body.
    Sources ground generation: linked topics keep drawing on them (F2)."""

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
    """The pedagogical director for one learning goal (ADR 002): mission,
    topic registry, phased attack plan, strategy dials, linked sources, and
    the append-only pedagogical journal. Lives at
    `campaigns/camp_<id>/campaign.md` with the syllabus as the body; the
    plan and journal are also projected to plan.yaml / changelog.md."""

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
    # Topic registry: {path, kind: recall|skill, summary, sr?} — skill topics
    # carry FSRS state here (ADR 012: memory attaches to the stable node).
    topics: List[Dict[str, Any]] = Field(default_factory=list)
    pedagogical_journal: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Omitted from frontmatter, maps to the Markdown file body
    syllabus_markdown: str = ""


class Exercise(StoredEntity):
    """A practice item in rotation. `kind` decides its scheduling life:
    recall repeats verbatim under FSRS (`sr` state on the exercise); skill
    items are disposable — their topic carries the FSRS state (ADR 012).
    `quality` tracks trust: reviewed / auto_accepted / diagnostic / spent /
    the skip verdicts (too_easy, too_hard, bad_quality) / archived."""

    _body_field: ClassVar[Optional[str]] = "prompt"

    id: str
    topic_path: str
    difficulty: str
    kind: str = "recall"  # recall: repeats verbatim under FSRS | skill: disposable, topic-scheduled (ADR 012)
    sr: Optional[Dict[str, Any]] = None  # FSRS card state (scheduling.py owns the shape)
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
    """A generated exercise awaiting human review (I2 trust gate) — same
    shape as Exercise minus scheduling state; promotion copies it into the
    rotation and deletes the candidate."""

    _body_field: ClassVar[Optional[str]] = "prompt"

    id: str
    topic_path: str
    difficulty: str
    kind: str = "recall"
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
    """One answer (or skip) to one exercise — the atomic unit of learning
    evidence. Stores the prompt as seen at the time, the learner's verbatim
    answer as the body, who graded it (`grader`, I10), and `reflected`, which
    tracks whether reflection has consumed it yet."""

    _body_field: ClassVar[Optional[str]] = "user_answer"

    id: str
    session_id: str
    exercise_id: str
    campaign_id: str
    score: float
    latency_seconds: float
    origin: Optional[str] = None  # "extension" marks appetite-mode evidence (dojo more); None = the ritual
    skip_reason: Optional[str] = None
    feedback: Optional[str] = None  # the learner's own comment (reflection input)
    grader: Optional[str] = None  # "exact" | "self" | "ai" — I10: who produced the score
    grade_run: Optional[str] = None  # the attempt.grade task whose trace backs an AI score
    grade_feedback: Optional[str] = None  # grader → learner, one correction
    grade_evidence: Optional[str] = None  # verbatim quote from the answer
    error_tag: Optional[str] = None  # compact pattern label, feeds reflection
    reflected: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    prompt: str = ""  # The prompt at the time of attempt
    # Omitted from frontmatter, maps to the Markdown file body
    user_answer: str = ""


class Insight(StoredEntity):
    """One hypothesis about the learner (ADR 004): a stable dotted `key`
    ("conditional.aux_choice", "feedback.user.…"), the description as body,
    and `sources` citing the attempt ids that evidence it. Reflection
    creates, updates, and resolves these; the learner can resolve directly
    (`dojo insights resolve --because`) — their reason lands in `resolution`
    verbatim and is the highest authority."""

    _body_field: ClassVar[Optional[str]] = "description"

    id: str
    key: str
    sources: List[str] = Field(default_factory=list)
    generation_run: Optional[str] = None
    status: str = "active"
    resolution: Optional[str] = None  # learner's own words when THEY resolved it
    topic_path: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Omitted from frontmatter, maps to the Markdown file body
    description: str


class Capture(StoredEntity):
    """A micro-source in the inbox (ADR 013): durable the instant it's spoken,
    filed later. status: unrouted → proposed (route awaiting confirmation, Q6)
    → filed | dismissed."""

    _body_field: ClassVar[Optional[str]] = "text"

    id: str
    status: str = "unrouted"
    why: Optional[str] = None  # the learner's own "because…" at capture time
    locator: Optional[str] = None  # where it came from (URL/file) — the agent fetches, dojo never does
    proposal: Optional[Dict[str, Any]] = None  # validated RouteResult + task id
    source_id: Optional[str] = None  # set when filed
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Omitted from frontmatter, maps to the Markdown file body
    text: str = ""


class Task(StoredEntity):
    """A pending unit of AI judgment (ADR 010) — the only seam between the
    deterministic core and whatever model fulfills it.

    The compiled prompt is the markdown body, so any fulfiller (harness,
    subprocess connector, future API worker) can be pointed at the file itself
    instead of re-emitting the payload through a conversation.
    """

    _body_field: ClassVar[Optional[str]] = "prompt"

    id: str
    kind: str  # exercise.generate | attempt.grade | campaign.reflect | campaign.plan | capture.route | goal.route
    status: str = "pending"  # pending | fulfilled | failed
    campaign_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)  # applier inputs (session_id, n_items, …)
    trace: List[Dict[str, Any]] = Field(default_factory=list)  # every submission verbatim (tail-clipped): at · ok · errors · raw
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
    """Workflow state for one sitting: the ordered exercise ids, a cursor,
    the reveal timestamp the latency clock runs from, and the packet/campaign
    reasons that `dojo why` replays (I9). Stored as JSON, not markdown —
    it's ephemeral machinery, not learning evidence."""

    id: str
    packet_reasons: Dict[str, str] = Field(default_factory=dict)  # exercise_id → why chosen (I9)
    campaign_reasons: Dict[str, str] = Field(default_factory=dict)  # Tier-1 ranking explained
    origin: str = "ritual"  # "extension" = a dojo more top-up; stamps its attempts
    status: str = "active"
    exercise_ids: List[str] = Field(default_factory=list)
    current_index: int = 0
    current_attempt_started_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
