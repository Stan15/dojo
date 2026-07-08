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
        "recent_rows": 500,
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
        "active_insights_with_ids": 800,
        "attempt_rows": 2560,
        "learner_feedback_or_none": 400,
    },
    "campaign.plan": {
        "goal_and_why": 400,
        "level_feedback_exclusions_or_none": 400,
        "registry_topic_paths_or_none": 800,
    },
    "capture.route": {
        "text_and_learner_note": 600,
        "campaign_lines_and_topic_paths": 1228,
    },
}

TOTAL_BUDGETS: dict[str, int] = {
    "exercise.generate": 7 * 1024,
    "exercise.diagnostic": 3 * 1024,
    "attempt.grade": 5 * 1024,
    "campaign.reflect": 6 * 1024,
    "campaign.plan": 4 * 1024,
    "capture.route": 3 * 1024,
}

TEMPLATES: dict[str, str] = {
    "exercise.generate": "exercise_generate.md",
    "exercise.diagnostic": "exercise_diagnostic.md",
    "attempt.grade": "attempt_grade.md",
    "campaign.reflect": "campaign_reflect.md",
    "campaign.plan": "campaign_plan.md",
    "capture.route": "capture_route.md",
}


@dataclass
class CompiledTask:
    kind: str
    prompt: str
    context: dict[str, Any]  # applier inputs, stored on the Task record
    truncated_sections: list[str] = field(default_factory=list)

    @property
    def payload_bytes(self) -> int:
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
    tier = store.configs.get_value("fulfiller.tier", "standard")
    return TIER_MULTIPLIER.get(str(tier), 1.0)


def _compile(store, kind: str, values: dict[str, Any], context: dict[str, Any]) -> CompiledTask:
    """Shared budget → clip → render → total-check pipeline for every kind."""
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

    total_budget = int(TOTAL_BUDGETS[kind] * mult)
    total = len(prompt.encode("utf-8"))
    if total > total_budget:
        raise BudgetExceeded(
            f"{kind} payload is {total}B, budget {total_budget}B — "
            "template or section budgets need rebalancing"
        )
    if truncated:
        context = {**context, "truncated_sections": truncated}
    return CompiledTask(kind=kind, prompt=prompt, context=context, truncated_sections=truncated)


# ------------------------------------------------------------------
# Section value builders — compact digests, never raw dumps (blueprint §9.1)
# ------------------------------------------------------------------

def strategy_line(campaign: Campaign) -> str:
    sp = campaign.strategy_profile or {}
    return (
        f"difficulty={sp.get('difficulty', 'intermediate')}, "
        f"scaffolding={sp.get('scaffolding', 'medium')}, "
        f"mode={sp.get('mode', 'practice')}"
    )


def insights_digest(store, campaign_id: str, k: int = 5) -> str:
    """Top-K active insights, one line each — the personalization loop's feed."""
    active = store.insights.list(campaign_id, filters={"status": "active"})
    lines = []
    for ins in active[-k:]:
        first_line = (ins.description or "").splitlines()[0] if ins.description else ""
        lines.append(f"- {ins.key}: {first_line}")
    return "\n".join(lines) if lines else "(no insights yet — first sessions)"


def recent_rows(store, campaign_id: str, n: int = 10) -> str:
    """Compact evidence rows: topic · score · signal. Never full bodies."""
    attempts = store.attempts.list(campaign_id)
    rows = []
    for a in attempts[-n:]:
        signal = a.skip_reason or (a.feedback.splitlines()[0][:40] if a.feedback else "")
        rows.append(f"{a.exercise_id} · score {a.score} · {signal}".rstrip(" ·"))
    return "\n".join(rows) if rows else "(no attempts yet)"


def source_section(source_slice: Optional[str]) -> str:
    if not source_slice:
        return ""
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
) -> CompiledTask:
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
        "insights_digest": insights_digest(store, campaign.id),
        "recent_rows": recent_rows(store, campaign.id),
        "source_section": source_section(source_slice),
    }
    context = {
        "campaign_id": campaign.id,
        "topic_path": topic_path,
        "n_items": n_items,
        "difficulty": difficulty,
        "mode": mode,
    }
    return _compile(store, "exercise.generate", values, context)


def compile_diagnostic(store, campaign: Campaign, *, topic_path: str, n_items: int) -> CompiledTask:
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
    active = store.insights.list(campaign.id, filters={"status": "active"})
    insight_lines = [
        f"- [{ins.id}] {ins.key}: {(ins.description or '').splitlines()[0]}"
        for ins in active
    ]
    attempts = store.attempts.list(campaign.id)
    window = attempts[-window_n:]
    unreflected = [a for a in attempts if not a.reflected and a not in window]
    rows = []
    for a in unreflected + window:
        signal = a.skip_reason or ""
        rows.append(f"{a.id} · {a.exercise_id} · score {a.score} · {signal}".rstrip(" ·"))
    feedback_lines = [
        f"- {a.feedback}" for a in window if a.feedback
    ]
    values = {
        "window_n": window_n,
        "mission": campaign.mission,
        "strategy_line": strategy_line(campaign),
        "active_insights_with_ids": "\n".join(insight_lines) or "(none)",
        "attempt_rows": "\n".join(rows) or "(none)",
        "learner_feedback_or_none": "\n".join(feedback_lines) or "(none)",
    }
    context = {
        "campaign_id": campaign.id,
        "window_n": window_n,
        "attempt_ids": [a.id for a in unreflected + window],
    }
    return _compile(store, "campaign.reflect", values, context)


def compile_plan(store, *, goal: str, context_notes: str = "", existing_topics: str = "") -> CompiledTask:
    values = {
        "goal_and_why": goal,
        "level_feedback_exclusions_or_none": context_notes or "(none)",
        "registry_topic_paths_or_none": existing_topics or "(none)",
    }
    return _compile(store, "campaign.plan", values, {"goal": goal})


def compile_route(store, *, capture_id: str, capture_text: str, learner_note: str = "") -> CompiledTask:
    campaigns = store.campaigns.list()
    registry_lines = []
    for camp in campaigns:
        registry_lines.append(f"campaign \"{camp.id}\": {camp.mission.splitlines()[0]}")
        topic_paths = sorted(
            {e.topic_path for e in store.exercises.list(camp.id)}
            | {t["path"] for t in (camp.topics or []) if t.get("path")}
        )
        for tp in topic_paths[:20]:
            registry_lines.append(f"  {tp}")
    text = capture_text if not learner_note else f"{capture_text}\n(learner note: {learner_note})"
    values = {
        "text_and_learner_note": text,
        "campaign_lines_and_topic_paths": "\n".join(registry_lines) or "(no campaigns yet)",
    }
    return _compile(store, "capture.route", values, {"capture_id": capture_id})
