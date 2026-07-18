"""Budgeted task-payload compilation (blueprint §9; invariant I6).

Every payload is assembled from ranked sections with byte budgets. The compiler
— never the model — owns all branching: grounded vs synthetic is a fragment
choice, diagnostic is its own template. Budgets scale with the optional
fulfiller tier (`fulfiller.tier`: frugal|standard|rich) so a large-context model
can be given richer grounding without ever being required (blueprint §9.3).

Sections are clipped hard at their budgets with a visible marker: truncation is
honest, never silent (I10).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..prompts import render
from ..schemas import Campaign, Exercise

TRUNCATION_MARK = "…[truncated]"

TIER_MULTIPLIER = {"frugal": 0.5, "standard": 1.0, "rich": 3.0}

# Per-section byte budgets at tier "standard" (design/prompts.md §2).
SECTION_BUDGETS: dict[str, dict[str, int]] = {
    "exercise.generate": {
        "strategy_line": 120,
        "mission": 200,
        "insights_digest": 600,
        "recent_rows": 768,  # presentations ride near-verbatim (ADR 017)
        "source_section": 4096,
    },
    "exercise.diagnostic": {
        "mission": 200,
        "insights_digest": 600,
    },
    "attempt.grade": {
        "exercise_prompt": 1024,
        "rubric_and_answer": 512,
        "user_answer": 2048,
    },
    "campaign.reflect": {
        "mission": 200,
        "strategy_line": 120,
        "plan_lines": 400,
        "active_insights_with_ids": 800,
        "trend_rows": 640,  # lifetime per-topic digest (ADR 017 §6)
        "attempt_rows": 2560,
        "learner_feedback_or_none": 400,
    },
    "campaign.plan": {
        "goal_and_why": 400,
        "level_feedback_exclusions_or_none": 400,
        "registry_topic_paths_or_none": 800,
        "existing_campaign_names_or_none": 300,  # ~4-word labels; dupe prevention (STATE 7f)
    },
    "capture.route": {
        "text_and_learner_note": 600,
        "campaign_lines_and_topic_paths": 1228,
    },
    "goal.route": {
        "goal_verbatim": 600,
        "campaign_lines_and_topic_paths": 1228,
    },
}

def total_budget(kind: str, skeleton_bytes: int, mult: float = 1.0) -> int:
    """The honest payload ceiling: the rendered skeleton (template + caps +
    non-section values) plus every section's scaled budget, plus slack for
    truncation markers. DERIVED, never a magic number — a static table
    silently went stale when templates grew and crashed the daily heartbeat
    on a full store (owner field crash 2026-07-16: reflect 8035B vs a 6144B
    constant last honest two eras ago). BudgetExceeded now fires only on
    true compiler bugs: a value that bypassed section clipping."""
    sections = sum(int(b * mult) for b in SECTION_BUDGETS[kind].values())
    return skeleton_bytes + sections + 128

TEMPLATES: dict[str, str] = {
    "exercise.generate": "exercise_generate.md",
    "exercise.diagnostic": "exercise_diagnostic.md",
    "attempt.grade": "attempt_grade.md",
    "campaign.reflect": "campaign_reflect.md",
    "campaign.plan": "campaign_plan.md",
    "capture.route": "capture_route.md",
    "goal.route": "goal_route.md",
}


@dataclass
class CompiledTask:
    """A ready-to-emit payload: the rendered prompt, the applier `context`
    stored on the Task record, and which sections were clipped."""

    kind: str
    prompt: str
    context: dict[str, Any]  # applier inputs, stored on the Task record
    truncated_sections: list[str] = field(default_factory=list)

    @property
    def payload_bytes(self) -> int:
        """UTF-8 size of the prompt — what the footprint gates measure."""
        return len(self.prompt.encode("utf-8"))


class BudgetExceeded(RuntimeError):
    """A compiled payload broke its total budget — a compiler bug, not model input."""


def clip(text: str, budget_bytes: int) -> tuple[str, bool]:
    """UTF-8-safe hard clip with a visible marker. Returns (text, was_clipped)."""
    raw = text.encode("utf-8")
    if len(raw) <= budget_bytes:
        return text, False
    mark = TRUNCATION_MARK.encode("utf-8")
    keep = max(0, budget_bytes - len(mark))
    clipped = raw[:keep].decode("utf-8", errors="ignore")
    return clipped + TRUNCATION_MARK, True


def _tier(store) -> float:
    tier = (store.configs.get_value("model.tier")
            or store.configs.get_value("fulfiller.tier", "standard"))
    return TIER_MULTIPLIER.get(str(tier), 1.0)


def _compile(store, kind: str, values: dict[str, Any], context: dict[str, Any]) -> CompiledTask:
    """Shared budget → clip → render → total-check pipeline for every kind.
    The kind's validator caps (limits.TEMPLATE_CAPS) are injected so templates
    interpolate exactly the limits they state — one source, never stale."""
    from .. import limits

    values = {**limits.TEMPLATE_CAPS.get(kind, {}), **values}
    mult = _tier(store)
    budgets = SECTION_BUDGETS[kind]
    truncated: list[str] = []
    clipped_values: dict[str, Any] = {}
    for key, val in values.items():
        if key in budgets and isinstance(val, str):
            budget = int(budgets[key] * mult)
            new_val, was_clipped = clip(val, budget)
            clipped_values[key] = new_val
            if was_clipped:
                truncated.append(key)
        else:
            clipped_values[key] = val

    prompt = render(TEMPLATES[kind], clipped_values)

    skeleton = render(TEMPLATES[kind], {
        **clipped_values, **{k: "" for k in budgets},
    })
    ceiling = total_budget(kind, len(skeleton.encode("utf-8")), mult)
    total = len(prompt.encode("utf-8"))
    if total > ceiling:
        raise BudgetExceeded(
            f"{kind} payload is {total}B, ceiling {ceiling}B — "
            "a section escaped its clip (compiler bug)"
        )
    if truncated:
        context = {**context, "truncated_sections": truncated}
    return CompiledTask(kind=kind, prompt=prompt, context=context, truncated_sections=truncated)


# ------------------------------------------------------------------
# Section value builders — compact digests, never raw dumps (blueprint §9.1)
# ------------------------------------------------------------------

def strategy_line(campaign: Campaign) -> str:
    """The strategy dials as one compact `k=v` line (defaults filled in)."""
    sp = campaign.strategy_profile or {}
    return (
        f"difficulty={sp.get('difficulty', 'intermediate')}, "
        f"scaffolding={sp.get('scaffolding', 'medium')}, "
        f"mode={sp.get('mode', 'practice')}"
    )


def targeted_insights(store, campaign_id: str, k: int = 5,
                      topic_path: Optional[str] = None):
    """The top-K active insights a payload will carry — one selection, used
    both for the digest text and for stamping their keys onto the task
    (`insights show` traces which exercises targeted a belief).

    Ranking: topic affinity first (an insight sharing a dotted segment with
    the generation target outranks unrelated ones), then `updated_at` —
    evidence freshness, not creation order, since reflection re-confirms
    long-standing beliefs by updating them."""
    active = store.insights.list(campaign_id, filters={"status": "active"})

    def rank(ins) -> tuple[int, str, str]:
        segments = set(ins.key.split(".")) | (
            set(ins.topic_path.split(".")) if ins.topic_path else set()
        )
        affinity = 1 if topic_path and segments & set(topic_path.split(".")) else 0
        return (affinity, ins.updated_at, ins.id)

    return sorted(active, key=rank)[-k:]


def insights_digest(store, campaign_id: str, k: int = 5,
                    topic_path: Optional[str] = None) -> str:
    """Top-K active insights, one line each — the personalization loop's feed."""
    lines = []
    for ins in targeted_insights(store, campaign_id, k, topic_path=topic_path):
        first_line = (ins.description or "").splitlines()[0] if ins.description else ""
        lines.append(f"- {ins.key}: {first_line}")
    return "\n".join(lines) if lines else "(no insights yet — first sessions)"


def recent_rows(store, campaign_id: str, topic_path: str = "", n: int = 8) -> str:
    """The topic's recent practice ARC (ADR 017 practice-history window):
    presentations near-verbatim — they are the content anchors later probes
    build on — probes and attempts as prompt glimpses with scores, relative
    days (anchored to the newest row, so goldens stay deterministic), plus
    one cross-topic calibration line. A WINDOW, not the whole record: wrong
    assumptions are structurally cheap (a probe on unseen material is just
    a free first-encounter miss), so this section informs, never gates."""
    from datetime import datetime

    attempts = store.attempts.list(campaign_id)
    exercises = {ex.id: ex for ex in store.exercises.list(campaign_id)}

    def on_topic(a) -> bool:
        ex = exercises.get(a.exercise_id)
        t = ex.topic_path if ex else None
        return bool(t) and (
            t == topic_path
            or t.startswith(topic_path + ".")
            or topic_path.startswith(t + ".")
        )

    topical = [a for a in attempts if on_topic(a)] if topic_path else list(attempts)
    window = topical[-n:]
    rows: list[str] = []
    if window:
        anchor = max(datetime.fromisoformat(a.created_at) for a in window)
        last_graded_at = max(
            (a.created_at for a in topical if a.grader not in (None, "exposure")),
            default="",
        )
        for a in window:
            ex = exercises.get(a.exercise_id)
            days = (anchor - datetime.fromisoformat(a.created_at)).days
            when = f"{days}d ago" if days else "recent"
            glimpse = (a.prompt or "").replace("\n", " ")[:40]
            if ex is not None and ex.kind == "present":
                material = (ex.answer or "").replace("\n", " ")[:90]
                tail = "" if last_graded_at > a.created_at else " (awaiting first recall)"
                rows.append(f'{when} · presented: "{material}"{tail}')
            elif a.grader == "exposure":
                rows.append(f'{when} · first contact, unscored · "{glimpse}"')
            elif a.skip_reason:
                rows.append(f"{when} · skipped ({a.skip_reason})")
            elif a.grader is None and a.score == 0.0:
                rows.append(f'{when} · ungraded · "{glimpse}"')
            else:
                rows.append(f'{when} · score {a.score} · "{glimpse}"')
    if topic_path:
        others = [
            a for a in attempts[-10:]
            if not on_topic(a) and not a.skip_reason
            and a.grader not in (None, "exposure")
        ]
        if others:
            mean = sum(a.score for a in others) / len(others)
            rows.append(f"other topics, last {len(others)} graded: mean {mean:.2f}")
        # Struggle travels, success aggregates (eval finding 2026-07-10:
        # topic-scoping this window collapsed the cross-topic struggle rows
        # calibration depends on): the most recent sub-0.7 rows ride along.
        for a in [a for a in others if a.score < 0.7][-2:]:
            glimpse = (a.prompt or "").replace("\n", " ")[:40]
            rows.append(
                f'nearby struggle · score {a.score} · {a.latency_seconds:.0f}s · "{glimpse}"'
            )
    return "\n".join(rows) if rows else "(no practice on this topic yet)"


def trend_rows(store, campaign: Campaign) -> str:
    """Lifetime per-topic digest (ADR 017 §6): reflection's sliding window
    is ~15 attempts, so months-scale patterns — over-mastery, staleness,
    fading interest — are structurally invisible to it. The core computes
    them deterministically; the model judges. Graded evidence only:
    exposure and knowledge-gap events never count toward mastery trends
    (a topic can never look 'mastered' off encodings). Day counts anchor
    to the campaign's newest attempt (determinism for goldens)."""
    from datetime import datetime

    attempts = store.attempts.list(campaign.id)
    topic_of = {ex.id: ex.topic_path for ex in store.exercises.list(campaign.id)}
    per: dict[str, list] = {}
    for a in attempts:
        if a.skip_reason or a.grader in (None, "exposure"):
            continue
        t = topic_of.get(a.exercise_id)
        if t:
            per.setdefault(t, []).append(a)
    anchor = (
        max(datetime.fromisoformat(a.created_at) for a in attempts)
        if attempts else None
    )
    rows: list[str] = []
    for t in (campaign.topics or [])[:12]:
        path = t.get("path")
        if not path:
            continue
        if t.get("retired"):
            rows.append(f"{path} · RETIRED ({t.get('retired_reason', 'learner request')})")
            continue
        atts = per.get(path, [])
        if not atts:
            rows.append(f"{path} · no graded practice yet")
            continue
        half = max(1, len(atts) // 2)
        early = sum(a.score for a in atts[:half]) / half
        late_n = len(atts) - half
        late = sum(a.score for a in atts[half:]) / late_n if late_n else early
        last_seen = (anchor - datetime.fromisoformat(atts[-1].created_at)).days
        last_miss = next((a for a in reversed(atts) if a.score < 0.7), None)
        miss_bit = (
            f"last miss {(anchor - datetime.fromisoformat(last_miss.created_at)).days}d ago"
            if last_miss else "never missed"
        )
        rows.append(
            f"{path} · {len(atts)} graded · acc {early:.2f}→{late:.2f} · "
            f"{miss_bit} · practiced {last_seen}d ago"
        )
    return "\n".join(rows) if rows else "(no topics registered)"


def source_section(source_slice: Optional[str], source_why: Optional[str] = None) -> str:
    """Wraps a grounding slice under a `## SOURCE` heading; empty when
    generation is synthetic. `source_why` carries the learner's own stated
    reason for saving the material (capture --why) — the generation aims at
    what THEY care about in it, not the material generally (owner core-need
    audit 2026-07-18, QUESTIONS 6g): why-scoped quizzing becomes structural
    instead of depending entirely on how narrowly the agent extracted."""
    if not source_slice:
        return ""
    if source_why:
        return (f"## SOURCE (the learner saved this because: {source_why} — "
                f"aim the practice at that)\n{source_slice}")
    return f"## SOURCE\n{source_slice}"


# ------------------------------------------------------------------
# One compile function per task kind
# ------------------------------------------------------------------

def compile_generate(
    store,
    campaign: Campaign,
    *,
    topic_path: str,
    n_items: int,
    difficulty: str,
    source_slice: Optional[str] = None,
    source_why: Optional[str] = None,
) -> CompiledTask:
    """Payload for `exercise.generate`: mission + strategy + insights digest +
    recent evidence rows, with the grounding rule chosen by whether a source
    slice is present (grounded extracts; synthetic may draw on model
    knowledge). The compiler picks the fragment — the model never branches."""
    mode = "grounded" if source_slice else "synthetic"
    grounding_rule = render(
        f"fragments/grounding_{mode}.md", {"n_items": n_items}
    )
    values = {
        "n_items": n_items,
        "topic_path": topic_path,
        "difficulty": difficulty,
        "grounding_rule": grounding_rule,
        "mission": campaign.mission,
        "strategy_line": strategy_line(campaign),
        "insights_digest": insights_digest(store, campaign.id, topic_path=topic_path),
        "recent_rows": recent_rows(store, campaign.id, topic_path=topic_path),
        "source_section": source_section(source_slice, source_why),
    }
    context = {
        "campaign_id": campaign.id,
        "topic_path": topic_path,
        "n_items": n_items,
        "difficulty": difficulty,
        "mode": mode,
        # Forward tracing (ownership block): which beliefs this generation
        # was steered by — `dojo insights show` counts the exercises back.
        "targeted_insights": [
            ins.key for ins in targeted_insights(store, campaign.id, topic_path=topic_path)
        ],
    }
    return _compile(store, "exercise.generate", values, context)


def compile_diagnostic(store, campaign: Campaign, *, topic_path: str, n_items: int) -> CompiledTask:
    """Payload for `exercise.diagnostic`: deliberately minimal (mission +
    insights only) — calibration questions probe the learner, so recent
    scores and sources would only bias them."""
    values = {
        "n_items": n_items,
        "topic_path": topic_path,
        "mission": campaign.mission,
        "insights_digest": insights_digest(store, campaign.id),
    }
    context = {
        "campaign_id": campaign.id,
        "topic_path": topic_path,
        "n_items": n_items,
        "mode": "diagnostic",
    }
    return _compile(store, "exercise.diagnostic", values, context)


def compile_grade(store, campaign: Campaign, exercise: Exercise, *, attempt_id: str, user_answer: str) -> CompiledTask:
    """Payload for `attempt.grade`: the exercise prompt, whatever rubric/
    answer exists (or an honest no-rubric instruction), and the learner's
    answer. No campaign context — grading must judge THIS answer only."""
    rubric_parts = []
    if exercise.answer:
        rubric_parts.append(f"Answer: {exercise.answer}")
    if exercise.rubric:
        rubric_parts.append(exercise.rubric)
    values = {
        "exercise_prompt": exercise.prompt,
        "rubric_and_answer": "\n".join(rubric_parts) or "(no rubric: judge correctness of content)",
        "user_answer": user_answer,
    }
    context = {
        "campaign_id": campaign.id,
        "attempt_id": attempt_id,
        "exercise_id": exercise.id,
    }
    return _compile(store, "attempt.grade", values, context)


def compile_reflect(store, campaign: Campaign, *, window_n: int = 15) -> CompiledTask:
    """Payload for `campaign.reflect`: the current attack plan (a revision the
    model can't see the plan for would be blind), active insights (with ids
    the model must cite), a sliding window of attempt rows (ADR 008) plus
    older unreflected ones, and verbatim learner feedback.
    `context.attempt_ids` lists exactly the graded rows that FIT the byte
    budget — those are the only citable ids, and the only ones marked
    reflected on apply."""
    plan_rows = []
    for i, p in enumerate(campaign.attack_plan):
        marker = " (done)" if i < campaign.active_phase_index else (
            " (active)" if i == campaign.active_phase_index else "")
        c = p.criteria
        plan_rows.append(
            f"phase {p.phase}{marker}: {', '.join(p.topics)} · "
            f"{c.min_attempts}+ @ {c.min_accuracy:.0%}"
            + (f" · {p.focus}" if p.focus else "")
        )
    # Topic hygiene (owner audit 2026-07-09): a revision that can't see the
    # registered-but-unscheduled topics can only invent new ones — show them
    # so reuse beats duplication here too.
    scheduled = {t for p in campaign.attack_plan for t in p.topics}
    unscheduled = sorted(
        t["path"] for t in (campaign.topics or [])
        if t.get("path") and t["path"] not in scheduled
    )
    if unscheduled:
        plan_rows.append(f"registered topics not yet in any phase: {', '.join(unscheduled)}")
    active = store.insights.list(campaign.id, filters={"status": "active"})
    insight_lines = [
        f"- [{ins.id}] {ins.key}: {(ins.description or '').splitlines()[0]}"
        for ins in active
    ]
    # Encoding events (grader="exposure", ADR 017) are information, not
    # learner evidence: they are pre-marked reflected and stay out of the
    # rows entirely — aggregate encoding activity reaches reflection via the
    # trend digest, not as pseudo-failures.
    attempts = [
        a for a in store.attempts.list(campaign.id) if a.grader != "exposure"
    ]
    window = attempts[-window_n:]
    unreflected = [a for a in attempts if not a.reflected and a not in window]

    # Integrity (use-case audit G1+H1): pending-grade attempts are labeled, not
    # counted as failures nor marked reflected; and only attempts whose rows
    # actually FIT the byte budget enter attempt_ids — anything clipped stays
    # unreflected for the next run instead of being silently skipped forever.
    row_budget = int(
        SECTION_BUDGETS["campaign.reflect"]["attempt_rows"] * _tier(store)
    )
    # Rows must carry what patterns are MADE OF (eval finding 2026-07-09:
    # latency and error tags were promised by design/prompts.md §5 but never
    # compiled — overconfidence and plateau patterns were structurally
    # invisible): topic (not opaque exercise ids), seconds taken, the
    # grader's error tag, skip reason, and the appetite-mode label.
    topic_of = {ex.id: ex.topic_path for ex in store.exercises.list(campaign.id)}
    rows: list[str] = []
    included_ids: list[str] = []
    used = 0
    for a in unreflected + window:
        # Provisional scores are ALWAYS 0.0 (submit_answer) — a graded wrong
        # answer carries grader="ai"/"exact"/"self". Legacy grader-less rows
        # with score 0.0 err toward "ungraded" (they stay unreflected — safe).
        pending = a.grader is None and a.score == 0.0 and not a.skip_reason
        # Appetite-mode evidence is labeled (QUESTIONS 2026-07-09): extension
        # rows come from learner-requested extra practice, not the ritual, so
        # reflection can weigh fatigue/novelty effects instead of absorbing
        # them blind.
        signal = " · ".join(filter(None, [
            a.error_tag or "",
            a.skip_reason or "",
            "extension (extra practice, learner-requested)" if a.origin == "extension" else "",
        ]))
        # A short answer glimpse (never the full body, blueprint §9): patterns
        # like "uses avoir for motion verbs" or "misreads the null" live in
        # WHAT the learner wrote, not in scores alone.
        glimpse = (a.user_answer or "").strip().replace("\n", " ")
        if len(glimpse) > 48:
            glimpse = glimpse[:47] + "…"
        row = (
            f"{a.id} · {topic_of.get(a.exercise_id, a.exercise_id)} · "
            + ("(ungraded — ignore the score)" if pending else f"score {a.score}")
            + f" · {a.latency_seconds:.0f}s"
            + (f" · {signal}" if signal else "")
            + (f' · "{glimpse}"' if glimpse and not pending else "")
        )
        cost = len(row.encode("utf-8")) + 1
        if used + cost > row_budget:
            break
        rows.append(row)
        used += cost
        if not pending:
            included_ids.append(a.id)
    feedback_lines = [
        f"- {a.feedback}" for a in window if a.feedback
    ]
    # A learner-resolved insight is the loudest feedback there is (contest =
    # highest authority): their verbatim reason rides along until the next
    # reflection has consumed it (timestamp-gated — no extra state).
    last_reflect = max(
        (e.get("timestamp", "") for e in campaign.pedagogical_journal
         if e.get("action") == "REFLECT"),
        default="",
    )
    for ins in store.insights.list(campaign.id, filters={"status": "resolved"}):
        if ins.resolution and ins.updated_at > last_reflect:
            feedback_lines.append(
                f'- [learner resolved insight {ins.key}] "{ins.resolution}"'
            )
    values = {
        "window_n": window_n,
        "mission": campaign.mission,
        "strategy_line": strategy_line(campaign),
        "plan_lines": "\n".join(plan_rows) or "(no plan yet)",
        "active_insights_with_ids": "\n".join(insight_lines) or "(none)",
        "trend_rows": trend_rows(store, campaign),
        "attempt_rows": "\n".join(rows) or "(none)",
        "learner_feedback_or_none": "\n".join(feedback_lines) or "(none)",
    }
    context = {
        "campaign_id": campaign.id,
        "window_n": window_n,
        "attempt_ids": included_ids,
    }
    return _compile(store, "campaign.reflect", values, context)


def compile_plan(store, *, goal: str, context_notes: str = "", existing_topics: str = "") -> CompiledTask:
    """Payload for `campaign.plan`: the learner's goal verbatim, optional
    level/constraint notes, existing topic paths so a new plan extends the
    registry instead of duplicating it, and existing campaign names so the
    generated name doesn't collide (the deterministic suffix floor still
    catches whatever slips through)."""
    names = ", ".join(sorted(c.name for c in store.campaigns.list())) or "(none)"
    values = {
        "goal_and_why": goal,
        "level_feedback_exclusions_or_none": context_notes or "(none)",
        "registry_topic_paths_or_none": existing_topics or "(none)",
        "existing_campaign_names_or_none": names,
    }
    return _compile(store, "campaign.plan", values, {"goal": goal})


def registry_digest(store) -> str:
    """The real campaign/topic registry as compact lines (mission + up to 20
    topic paths per campaign) — routers may only file into places that exist
    (ADR 013)."""
    lines = []
    for camp in store.campaigns.list():
        lines.append(f"campaign \"{camp.id}\": {camp.mission.splitlines()[0]}")
        topic_paths = sorted(
            {e.topic_path for e in store.exercises.list(camp.id)}
            | {t["path"] for t in (camp.topics or []) if t.get("path")}
        )
        for tp in topic_paths[:20]:
            lines.append(f"  {tp}")
    return "\n".join(lines)


def compile_route(store, *, capture_id: str, capture_text: str, learner_note: str = "") -> CompiledTask:
    """Payload for `capture.route`: the capture text (+ learner note) and the
    registry digest."""
    text = capture_text if not learner_note else f"{capture_text}\n(learner note: {learner_note})"
    values = {
        "text_and_learner_note": text,
        "campaign_lines_and_topic_paths": registry_digest(store) or "(no campaigns yet)",
    }
    return _compile(store, "capture.route", values, {"capture_id": capture_id})


def compile_goal_route(store, *, goal: str) -> CompiledTask:
    """Payload for `goal.route` (route-first entry, QUESTIONS 2026-07-09): the
    learner's goal verbatim and the registry digest, so a near-fit goal extends
    an existing campaign instead of spawning a semantic duplicate. Cheapest
    task first: same 3 KB class as capture routing."""
    values = {
        "goal_verbatim": goal,
        "campaign_lines_and_topic_paths": registry_digest(store) or "(no campaigns yet)",
    }
    return _compile(store, "goal.route", values, {"goal": goal})
