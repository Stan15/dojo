"""Emit-side task flows: the deterministic triggers that request AI judgment.

Each flow decides *whether* a task is warranted (deterministic policy — the
model never chooses to run itself), compiles the budgeted payload, and emits a
pending Task. Nothing here blocks on AI (I4): callers report emitted tasks in
their envelopes and continue.
"""
from __future__ import annotations

from typing import Any, Optional

from ..schemas import Attempt, Campaign, Exercise, Task
from . import compiler, service


def task_ref(task: Task) -> dict[str, Any]:
    """The envelope form of a pending task: what a fulfiller needs, nothing else."""
    return {
        "id": task.id,
        "kind": task.kind,
        "prompt_file": f"tasks/{task.id}.md",
        "submit_with": f"dojo task submit {task.id}",
        "payload_bytes": task.payload_bytes,
    }


def request_reflection(store, campaign_id: str) -> Optional[Task]:
    """Emit a reflection task if there is unreflected evidence; else None.
    Deterministic trigger — reflection without new evidence is churn."""
    campaign = store.campaigns.get(campaign_id)
    if campaign is None:
        raise ValueError(f"campaign {campaign_id} not found")
    attempts = store.attempts.list(campaign_id)
    if not any(not a.reflected for a in attempts):
        return None
    compiled = compiler.compile_reflect(store, campaign)
    return service.emit(store, compiled)


def request_generation(
    store,
    campaign: Campaign,
    *,
    topic_path: str,
    n_items: int,
    difficulty: Optional[str] = None,
    source_slice: Optional[str] = None,
    diagnostic: bool = False,
) -> Task:
    if diagnostic:
        compiled = compiler.compile_diagnostic(
            store, campaign, topic_path=topic_path, n_items=n_items
        )
    else:
        compiled = compiler.compile_generate(
            store, campaign,
            topic_path=topic_path, n_items=n_items,
            difficulty=difficulty or campaign.strategy_profile.get("difficulty", "intermediate"),
            source_slice=source_slice,
        )
    return service.emit(store, compiled)


def request_grade(store, campaign: Campaign, exercise: Exercise, attempt: Attempt) -> Task:
    compiled = compiler.compile_grade(
        store, campaign, exercise,
        attempt_id=attempt.id, user_answer=attempt.user_answer or "",
    )
    return service.emit(store, compiled)


def request_plan(store, *, goal: str, context_notes: str = "", existing_topics: str = "") -> Task:
    compiled = compiler.compile_plan(
        store, goal=goal, context_notes=context_notes, existing_topics=existing_topics
    )
    return service.emit(store, compiled)
