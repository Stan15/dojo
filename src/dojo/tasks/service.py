"""Task lifecycle: emit → submit → apply.

This module is the I5 boundary (blueprint §6): submission is the ONLY path by
which AI output mutates state. The pipeline per submission:

    parse JSON (salvaging fenced/wrapped output)
      → validate against the task kind's result schema (limits enforced)
      → applier cross-checks (mechanical, store-aware: counts, substrings,
        target existence) and state mutation

Any failure rejects the submission with actionable errors and leaves domain
state untouched; the task records the attempt (`submissions`, `error_history`)
and fails permanently after `max_submissions` (honest degradation, I4/I10).
Every applier is idempotent: resubmitting a fulfilled task is a no-op, and the
state an applier writes is keyed by the task id, so a retried apply overwrites
itself rather than duplicating.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from pydantic import ValidationError

from .. import limits
from ..schemas import (
    Candidate,
    GenerateResult,
    GradeResult,
    Insight,
    PlanResult,
    ReflectResult,
    RESULT_SCHEMAS,
    Task,
)
from .compiler import CompiledTask

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def emit(store, compiled: CompiledTask) -> Task:
    """Persists a pending Task for any fulfiller to pick up."""
    task = Task(
        id=f"tsk_{uuid.uuid4().hex[:8]}",
        kind=compiled.kind,
        campaign_id=compiled.context.get("campaign_id"),
        context=compiled.context,
        payload_bytes=compiled.payload_bytes,
        prompt=compiled.prompt,
    )
    store.tasks.save(task)
    return task


def extract_json(raw: str) -> Any:
    """Salvages a JSON object from model output: bare, fenced, or embedded in
    prose. Harness CLIs (e.g. `codex exec`) echo the prompt — which itself
    contains JSON skeletons — before the answer, so when several top-level
    objects appear, the LAST one wins: the answer always follows the echo.
    Raises ValueError with a plain message when nothing parses."""
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for fenced in reversed(_FENCE.findall(text)):
        try:
            return json.loads(fenced.strip())
        except json.JSONDecodeError:
            continue

    decoder = json.JSONDecoder()
    last_obj, pos = None, 0
    while True:
        start = text.find("{", pos)
        if start == -1:
            break
        try:
            obj, end = decoder.raw_decode(text[start:])
            if isinstance(obj, dict):
                last_obj = obj
            pos = start + end  # skip objects nested inside this parse
        except json.JSONDecodeError:
            pos = start + 1
    if last_obj is not None:
        return last_obj
    raise ValueError("no JSON object found in the submission")


@dataclass
class SubmitOutcome:
    ok: bool
    task_id: str
    status: str  # task status after this submission
    errors: list[str] = field(default_factory=list)
    applied: Optional[dict[str, Any]] = None


def submit(store, task_id: str, raw: str) -> SubmitOutcome:
    task = store.tasks.get(task_id)
    if task is None:
        return SubmitOutcome(ok=False, task_id=task_id, status="unknown",
                             errors=[f"no such task: {task_id}"])
    if task.status == "fulfilled":
        # Idempotent: the work is done; repeating it must not duplicate state.
        return SubmitOutcome(ok=True, task_id=task_id, status="fulfilled",
                             applied={"note": "already fulfilled; submission ignored"})
    if task.status == "failed":
        return SubmitOutcome(ok=False, task_id=task_id, status="failed",
                             errors=["task already failed; re-emit it instead of resubmitting"])

    errors = _validate_and_apply(store, task, raw)
    task.submissions += 1
    task.response_bytes = len(raw.encode("utf-8"))
    task.updated_at = datetime.now(timezone.utc).isoformat()

    if errors:
        task.error_history.extend(errors[:5])
        if task.submissions >= task.max_submissions:
            task.status = "failed"
        store.tasks.save(task)
        return SubmitOutcome(ok=False, task_id=task_id, status=task.status, errors=errors)

    task.status = "fulfilled"
    store.tasks.save(task)
    return SubmitOutcome(ok=True, task_id=task_id, status="fulfilled", applied=task.context.get("_applied"))


def _validate_and_apply(store, task: Task, raw: str) -> list[str]:
    """Returns [] on success (with task.context['_applied'] set), else errors.
    Domain state is only touched by the applier, which runs last, after every
    check that can fail has passed."""
    schema = RESULT_SCHEMAS.get(task.kind)
    if schema is None:
        return [f"no result schema for task kind {task.kind!r}"]
    try:
        data = extract_json(raw)
    except ValueError as e:
        return [str(e)]
    try:
        result = schema.model_validate(data)
    except ValidationError as e:
        return [f"{err['loc']}: {err['msg']}" for err in e.errors()[:8]]

    applier = APPLIERS.get(task.kind)
    if applier is None:
        return [f"no applier for task kind {task.kind!r}"]
    try:
        applied = applier(store, task, result)
    except ApplyRejection as e:
        return list(e.reasons)
    task.context["_applied"] = applied
    return []


class ApplyRejection(Exception):
    """Mechanical cross-check failure: valid JSON, wrong facts. State untouched."""

    def __init__(self, *reasons: str):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


# ------------------------------------------------------------------
# Appliers — idempotent, total, and the only writers of AI-derived state
# ------------------------------------------------------------------

def apply_generate(store, task: Task, result: GenerateResult) -> dict[str, Any]:
    ctx = task.context
    campaign_id = ctx["campaign_id"]
    n_items = int(ctx["n_items"])
    diagnostic = ctx.get("mode") == "diagnostic"

    if result.intervention is not None:
        # Meta-learning escape hatch (prompt rule 9): the model judged that
        # meaningful exercises can't be written yet. Its questions enter the
        # normal loop as diagnostic items — answers feed reflection, which
        # sharpens the mission/profile; nothing special-cased downstream.
        if diagnostic:
            raise ApplyRejection(
                "diagnostic tasks cannot intervene — they ARE the clarifying questions"
            )
        from ..schemas import Exercise

        ids = []
        for i, question in enumerate(result.intervention.questions):
            ex_id = f"ex_{task.id[4:]}_iv{i}"  # task-derived: re-apply overwrites
            store.exercises.save(campaign_id, Exercise(
                id=ex_id,
                topic_path=ctx["topic_path"],
                difficulty=ctx.get("difficulty", "intermediate"),
                generation_run=task.id,
                quality="diagnostic",
                prompt=question,
            ))
            ids.append(ex_id)
        return {
            "intervention": result.intervention.model_dump(),
            "exercises": ids,
            "note": "generation declined pending answers to the questions above",
        }

    reasons = []
    if len(result.items) > n_items:
        reasons.append(f"asked for exactly {n_items} items, got {len(result.items)}")
    if len(result.items) < n_items and not result.note:
        reasons.append(f"fewer than {n_items} items requires a 'note' explaining why")
    for i, item in enumerate(result.items):
        if diagnostic:
            if item.skill != "diagnostic":
                reasons.append(f"items[{i}].skill must be 'diagnostic'")
            if limits.word_count(item.prompt) > limits.DIAGNOSTIC_PROMPT_WORDS:
                reasons.append(
                    f"items[{i}].prompt exceeds {limits.DIAGNOSTIC_PROMPT_WORDS} words"
                )
        else:
            if item.skill == "diagnostic":
                reasons.append(f"items[{i}].skill 'diagnostic' not valid for practice generation")
            if not item.answer or not item.rubric:
                reasons.append(f"items[{i}] needs both answer and rubric")
    if reasons:
        raise ApplyRejection(*reasons)

    ids = []
    for i, item in enumerate(result.items):
        if diagnostic:
            # Diagnostics bypass the candidate gate (I2 note): the learner
            # answering them IS the review — there is no content to trust.
            ex_id = f"ex_{task.id[4:]}_{i}"  # task-derived: re-apply overwrites
            from ..schemas import Exercise

            store.exercises.save(campaign_id, Exercise(
                id=ex_id,
                topic_path=ctx["topic_path"],
                difficulty=ctx.get("difficulty", "intermediate"),
                generation_run=task.id,
                quality="diagnostic",
                prompt=item.prompt,
            ))
            ids.append(ex_id)
        else:
            cand_id = f"cand_{task.id[4:]}_{i}"  # task-derived: re-apply overwrites
            store.candidates.save(campaign_id, Candidate(
                id=cand_id,
                topic_path=ctx["topic_path"],
                difficulty=ctx.get("difficulty", "intermediate"),
                generation_run=task.id,
                quality="candidate",
                answer=item.answer,
                rubric=item.rubric,
                prompt=item.prompt,
            ))
            ids.append(cand_id)
    key = "exercises" if diagnostic else "candidates"
    return {key: ids, "note": result.note}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def apply_grade(store, task: Task, result: GradeResult) -> dict[str, Any]:
    ctx = task.context
    campaign_id, attempt_id = ctx["campaign_id"], ctx["attempt_id"]
    attempt = store.attempts.get(campaign_id, attempt_id)
    if attempt is None:
        raise ApplyRejection(f"attempt {attempt_id} not found in campaign {campaign_id}")

    # The anti-hallucination anchor (design/prompts.md §4): the quoted evidence
    # must actually occur in the learner's answer.
    if _normalize(result.evidence) not in _normalize(attempt.user_answer or ""):
        raise ApplyRejection(
            "evidence is not a verbatim quote from the answer — re-read ANSWER and quote it"
        )

    attempt.score = result.score
    attempt.grader = "ai"
    attempt.grade_evidence = result.evidence
    attempt.grade_feedback = result.feedback
    attempt.error_tag = result.error_tag
    store.attempts.save(campaign_id, attempt)
    return {"attempt_id": attempt_id, "score": result.score, "error_tag": result.error_tag}


def apply_reflect(store, task: Task, result: ReflectResult) -> dict[str, Any]:
    ctx = task.context
    campaign_id = ctx["campaign_id"]
    campaign = store.campaigns.get(campaign_id)
    if campaign is None:
        raise ApplyRejection(f"campaign {campaign_id} not found")

    seen_attempts = set(ctx.get("attempt_ids", []))
    existing = {ins.id: ins for ins in store.insights.list(campaign_id)}

    # Every citation must point at evidence the model was actually shown, and
    # every touched insight must exist — weak models cannot invent references.
    reasons = []
    for i, upd in enumerate(result.insight_updates):
        for ev in upd.evidence:
            if ev not in seen_attempts:
                reasons.append(f"insight_updates[{i}] cites unknown attempt id {ev!r}")
        if upd.op in ("update", "resolve") and upd.id not in existing:
            reasons.append(f"insight_updates[{i}] targets unknown insight id {upd.id!r}")
    if reasons:
        raise ApplyRejection(*reasons)

    created, updated, resolved = [], [], []
    for i, upd in enumerate(result.insight_updates):
        if upd.op == "create":
            ins_id = f"ins_{task.id[4:]}_{i}"  # task-derived: re-apply overwrites
            store.insights.save(campaign_id, Insight(
                id=ins_id, key=upd.key, description=upd.text,
                sources=list(upd.evidence), generation_run=task.id,
            ))
            created.append(ins_id)
        elif upd.op == "update":
            ins = existing[upd.id]
            ins.description = upd.text
            ins.sources = list(dict.fromkeys([*ins.sources, *upd.evidence]))
            ins.updated_at = datetime.now(timezone.utc).isoformat()
            store.insights.save(campaign_id, ins)
            updated.append(upd.id)
        else:
            ins = existing[upd.id]
            ins.status = "resolved"
            ins.updated_at = datetime.now(timezone.utc).isoformat()
            store.insights.save(campaign_id, ins)
            resolved.append(upd.id)

    if result.strategy:
        if result.strategy.difficulty:
            campaign.strategy_profile["difficulty"] = result.strategy.difficulty
        if result.strategy.scaffolding:
            campaign.strategy_profile["scaffolding"] = result.strategy.scaffolding
    if result.plan_revision:
        campaign.attack_plan = result.plan_revision.phases

    campaign.pedagogical_journal.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "REFLECT",
        "trigger": f"reflection over {len(seen_attempts)} attempts (task {task.id})",
        "status": "applied",
        "hypothesis": result.journal,
    })
    campaign.updated_at = datetime.now(timezone.utc).isoformat()
    store.campaigns.save(campaign)

    for att_id in seen_attempts:
        att = store.attempts.get(campaign_id, att_id)
        if att and not att.reflected:
            att.reflected = True
            store.attempts.save(campaign_id, att)

    return {
        "created": created, "updated": updated, "resolved": resolved,
        "strategy_changed": result.strategy is not None,
        "plan_revised": result.plan_revision is not None,
        "journal": result.journal,
    }


def apply_plan(store, task: Task, result: PlanResult) -> dict[str, Any]:
    """Deliberately writes NO domain state (review-before-trust, I2): the
    fulfilled task carries the proposal; `dojo campaign create` materializes it
    deterministically after the learner confirms."""
    return {
        "mission": result.mission,
        "topics": [t.model_dump() for t in result.topics],
        "phases": [p.model_dump() for p in result.phases],
        "refinement_questions": result.refinement_questions,
    }


APPLIERS: dict[str, Callable[..., dict[str, Any]]] = {
    "exercise.generate": apply_generate,
    "exercise.diagnostic": apply_generate,
    "attempt.grade": apply_grade,
    "campaign.reflect": apply_reflect,
    "campaign.plan": apply_plan,
}
