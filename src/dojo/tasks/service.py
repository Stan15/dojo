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
    RouteResult,
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
    """What `submit` tells the fulfiller: success, the task's new status,
    actionable `errors` on rejection, and the applier's `applied` summary."""

    ok: bool
    task_id: str
    status: str  # task status after this submission
    errors: list[str] = field(default_factory=list)
    applied: Optional[dict[str, Any]] = None


def submit(store, task_id: str, raw: str) -> SubmitOutcome:
    """The one door for AI output (I5): parse → schema-validate → applier.

    Rejections record the errors on the task and count toward
    `max_submissions` (then the task fails permanently — honest degradation).
    Resubmitting a fulfilled task is an acknowledged no-op; a failed task
    must be re-emitted, not retried."""
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
    """Lands generation output. Four paths: an intervention becomes diagnostic
    exercises (its questions enter the normal loop); diagnostic items land as
    exercises directly (answering them IS the review); `auto_promote` items
    (daily replenishment) land as exercises under the queue cap; everything
    else lands as candidates awaiting review (I2). Cross-checks: exact item
    count (fewer needs a note), diagnostic/practice skill consistency,
    answer+rubric present on practice items."""
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

    if ctx.get("auto_promote"):
        # Daily replenishment (use-case audit J1): recorded auto-accept policy
        # (I2) — otherwise skill stock lands as candidates nothing in the daily
        # loop promotes, and the lane starves. The queue cap still holds.
        from ..schemas import Exercise

        active = [
            ex for ex in store.exercises.list(campaign_id)
            if ex.quality not in ("archived", "too_easy", "too_hard", "bad_quality", "spent")
        ]
        room = max(0, 20 - len(active))
        ids, skipped = [], 0
        for i, item in enumerate(result.items):
            if i >= room:
                skipped += 1
                continue
            ex_id = f"ex_{task.id[4:]}_{i}"  # task-derived: re-apply overwrites
            store.exercises.save(campaign_id, Exercise(
                id=ex_id,
                topic_path=ctx["topic_path"],
                difficulty=ctx.get("difficulty", "intermediate"),
                kind="recall" if item.skill == "recall" else "skill",
                generation_run=task.id,
                quality="auto_accepted",
                answer=item.answer,
                rubric=item.rubric,
                prompt=item.prompt,
            ))
            ids.append(ex_id)
        applied: dict[str, Any] = {"exercises": ids, "note": result.note}
        if skipped:
            applied["skipped_queue_cap"] = skipped
        return applied

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
                kind="recall" if item.skill == "recall" else "skill",
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
    """Lands a grade: rejects unless `evidence` is a verbatim quote from the
    learner's answer (the anti-hallucination anchor), then finalizes the
    attempt's score and advances the FSRS memory model — the step
    deliberately skipped while the score was provisional."""
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

    # The grade is final: advance the memory model now (ADR 014). Pending
    # attempts deliberately skipped this at answer time.
    from ..outcomes import land_score

    land_score(
        store, campaign_id, ctx["exercise_id"],
        score=result.score, latency_seconds=attempt.latency_seconds,
    )

    return {"attempt_id": attempt_id, "score": result.score, "error_tag": result.error_tag}


def apply_reflect(store, task: Task, result: ReflectResult) -> dict[str, Any]:
    """Lands a reflection: insight creates/updates/resolves (every citation —
    insight AND plan — must be an attempt id the model was shown; every
    touched insight must exist), strategy-dial changes, a journal entry, and
    marks the consumed attempts reflected.

    Plan revisions pass through change authority (`authority.py`): minor or
    learner-asked-for changes apply with a revertable snapshot; major
    inferred restructures become a pending proposal for `dojo plan confirm`.
    `questions` become diagnostic exercises whose answers feed later
    reflections as citable evidence."""
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
    if result.plan_revision:
        for ev in result.plan_revision.evidence:
            if ev not in seen_attempts:
                reasons.append(f"plan_revision cites unknown attempt id {ev!r}")
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

    # Plan changes go through change authority (authority.py): the learner's
    # plan is a contract. Minor/asked-for → apply, journaled with a pre-change
    # snapshot and announced by the next daily; major inferred → a PENDING
    # proposal the learner resolves (dojo plan confirm|reject). The rest of
    # the reflection is never held hostage by the gate.
    plan_outcome = None
    if result.plan_revision:
        from . import authority

        user_initiated = authority.revision_is_user_initiated(
            store, campaign_id, result.plan_revision.evidence
        )
        baseline = authority.confirmed_plan_baseline(campaign) or campaign.attack_plan
        delta = authority.classify_plan_delta(baseline, result.plan_revision.phases)
        if user_initiated or delta == "minor":
            campaign.pedagogical_journal.append(authority.journal_entry(
                authority.PLAN_APPLIED,
                reason=result.plan_revision.reason, task_id=task.id,
                plan_snapshot=campaign.attack_plan,
            ))
            campaign.attack_plan = result.plan_revision.phases
            plan_outcome = "applied"
        else:
            # One live proposal per campaign: a newer reflection's view
            # supersedes an unresolved older one.
            stale = authority.pending_proposal(campaign)
            if stale is not None:
                stale["status"] = "superseded"
            campaign.pedagogical_journal.append(authority.journal_entry(
                authority.PLAN_PROPOSED,
                reason=result.plan_revision.reason, task_id=task.id,
                plan_snapshot=campaign.attack_plan,
                proposed=result.plan_revision.phases,
            ))
            plan_outcome = "proposed"

    # Ask-don't-restructure: questions become diagnostic exercises in the
    # normal loop (mirror of generation's intervention); the learner's answers
    # are attempts a later reflection can cite as evidence for a revision.
    question_ids = []
    if result.questions:
        from ..schemas import Exercise

        topic = campaign.topic_path or "general"
        for i, q in enumerate(result.questions):
            ex_id = f"ex_{task.id[4:]}_rq{i}"  # task-derived: re-apply overwrites
            store.exercises.save(campaign_id, Exercise(
                id=ex_id,
                topic_path=topic,
                difficulty="intermediate",
                generation_run=task.id,
                quality="diagnostic",
                prompt=q,
            ))
            question_ids.append(ex_id)

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
        "plan_revised": plan_outcome == "applied",
        "plan_proposed": plan_outcome == "proposed",
        "questions_as_diagnostics": question_ids,
        "journal": result.journal,
        **({"next": f"a plan restructure awaits the learner: dojo plan confirm --campaign {campaign_id} (or reject)"}
           if plan_outcome == "proposed" else {}),
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


def apply_route(store, task: Task, result: RouteResult) -> dict[str, Any]:
    """Validates a route against the real registry (ADR 013: weak models cannot
    file into places that don't exist), stores it as a PROPOSAL awaiting
    confirmation (Q6 default), and auto-files only when capture.autofile is on
    and confidence is high."""
    from ..filing import file_capture, known_topic_paths

    capture = store.captures.get(task.context["capture_id"])
    if capture is None:
        raise ApplyRejection(f"capture {task.context['capture_id']!r} not found")

    if result.action in ("attach", "new_topic"):
        campaign = store.campaigns.get(result.campaign)
        if campaign is None:
            raise ApplyRejection(
                f"campaign {result.campaign!r} is not in the registry — copy names exactly"
            )
        known = known_topic_paths(store, campaign)
        if result.action == "attach" and result.topic_path not in known:
            raise ApplyRejection(
                f"topic {result.topic_path!r} does not exist in {result.campaign!r} — "
                "attach only to listed topics, or use new_topic"
            )
        if result.action == "new_topic":
            parent = ".".join(result.topic_path.split(".")[:-1])
            if parent and parent not in known and not any(
                p.startswith(parent) for p in known
            ):
                raise ApplyRejection(
                    f"new_topic parent {parent!r} does not exist in {result.campaign!r} — "
                    "hang the new leaf off a listed path"
                )

    proposal = result.model_dump()
    capture.proposal = {**proposal, "task_id": task.id}
    capture.status = "unrouted" if result.action == "stay_inbox" else "proposed"
    capture.updated_at = datetime.now(timezone.utc).isoformat()
    store.captures.save(capture)

    autofile = str(store.configs.get_value("capture.autofile", "false")).lower() == "true"
    if (
        autofile and result.confidence == "high"
        and result.action in ("attach", "new_topic")
    ):
        filed = file_capture(store, capture, proposal)
        return {"routed": proposal, "filed": filed}

    return {
        "routed": proposal,
        "filed": None,
        "next": (
            "the route awaits the learner's confirmation: dojo inbox confirm "
            f"{capture.id} (or dismiss / re-route)"
        ) if capture.status == "proposed" else "capture stays in the inbox",
    }


APPLIERS: dict[str, Callable[..., dict[str, Any]]] = {
    "exercise.generate": apply_generate,
    "exercise.diagnostic": apply_generate,
    "attempt.grade": apply_grade,
    "campaign.reflect": apply_reflect,
    "campaign.plan": apply_plan,
    "capture.route": apply_route,
}
