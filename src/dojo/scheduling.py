"""Retention scheduling behind a dojo-owned boundary (ADR 014).

py-fsrs (FSRS-6, MIT) does the memory math; this module is the only place that
knows it. Everything crossing the boundary is dojo vocabulary: score bands
(ADR 010 grading language), latency, skip reasons, and a plain `sr` dict that
lives in entity frontmatter (I7 round-trips it like any other field).

Determinism (I8): every function takes an explicit `now`; nothing here reads
the wall clock on its own. The LLM is never involved — scores land, math runs,
dates come out, identical under any model.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fsrs import Card, Rating, Scheduler

# One scheduler, default FSRS-6 parameters, fuzzing OFF: py-fsrs fuzzes
# intervals via global random by default, which would break I8 (same state,
# same clock → same schedule) and every golden/property test above it.
# Per-learner parameter fitting stays backlog (ADR 014).
_scheduler = Scheduler(enable_fuzzing=False)

# A perfect answer produced this fast signals fluency beyond mere correctness
# (pedagogy-foundation: fluency vs storage strength) — it earns Easy.
FAST_LATENCY_SECONDS = 15.0


def rating_for(
    score: float,
    latency_seconds: Optional[float] = None,
    skip_reason: Optional[str] = None,
) -> Rating:
    """ADR 014's one mapping: dojo evidence → FSRS rating.

    0.0/0.3 → Again; 0.7 → Hard; 1.0 → Good; 1.0-and-fast or a too_easy skip →
    Easy; a "forgot" skip → Again (retrieval failed, keep it coming back).
    """
    if skip_reason == "too_easy":
        return Rating.Easy
    if skip_reason == "forgot":
        return Rating.Again
    if score >= 1.0:
        if latency_seconds is not None and latency_seconds <= FAST_LATENCY_SECONDS:
            return Rating.Easy
        return Rating.Good
    if score >= 0.7:
        return Rating.Hard
    return Rating.Again


def new_state(now: datetime) -> dict[str, Any]:
    """A fresh memory: due immediately."""
    card = Card(due=now)
    return card.to_dict()


def record_outcome(
    sr: Optional[dict[str, Any]],
    *,
    score: float,
    latency_seconds: Optional[float] = None,
    skip_reason: Optional[str] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Advances the memory model with one piece of evidence; returns the new
    state (callers persist it — this function owns no IO)."""
    now = now or datetime.now(timezone.utc)
    card = Card.from_dict(sr) if sr else Card(due=now)
    rating = rating_for(score, latency_seconds, skip_reason)
    card, _log = _scheduler.review_card(card, rating, review_datetime=now)
    return card.to_dict()


def due_at(sr: Optional[dict[str, Any]]) -> Optional[datetime]:
    if not sr or not sr.get("due"):
        return None
    return datetime.fromisoformat(sr["due"])


def is_due(sr: Optional[dict[str, Any]], now: datetime) -> bool:
    """No state = never practiced = due now (a new memory wants forming)."""
    due = due_at(sr)
    return True if due is None else due <= now


def retrievability(sr: Optional[dict[str, Any]], now: datetime) -> float:
    """Estimated recall probability right now (0..1); 0 for never-practiced.
    Powers `dojo why`/`stats` honesty — an estimate, tagged as such (I10)."""
    if not sr or not sr.get("last_review"):
        return 0.0
    return float(_scheduler.get_card_retrievability(Card.from_dict(sr), now))
