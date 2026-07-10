"""Score landing: the single implementation that advances memory models when a
FINAL score exists (ADR 012/014).

recall exercises → FSRS on the item. skill exercises → FSRS on the campaign's
topic node, and the item retires (novelty principle: skill items are
disposable). Diagnostics are information-gathering, never memories.

Both the API (deterministic grades, skips, corrections) and the grade applier
(AI grades) land through here — two callers, one truth.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from . import scheduling


def first_encounter(campaign, ex) -> bool:
    """ADR 017 predicate: would a score land on never-encoded material?

    True only for model-invented (`provenance: synthetic`) practice items
    whose lane has no memory state yet — skill items check the topic node,
    recall items their own card. Grounded material (from a source/capture
    the learner already met in life) and diagnostics are never encoding
    candidates; an item with no stored answer has no kernel to reveal, so
    it cannot serve as an encoding event either."""
    if ex is None or ex.quality == "diagnostic" or not ex.answer:
        return False
    if ex.kind == "present":
        return True  # a presentation is BY DEFINITION an encoding event
    if getattr(ex, "provenance", "synthetic") == "grounded":
        return False
    if ex.kind == "skill":
        entry = next(
            (t for t in ((campaign.topics if campaign else None) or [])
             if t.get("path") == ex.topic_path),
            None,
        )
        return entry is None or not entry.get("sr")
    return ex.sr is None


def land_exposure(
    store, campaign_id: str, exercise_id: str, *, now: Optional[datetime] = None
) -> None:
    """Lands an encoding event (ADR 017): initializes the lane's memory with
    a fixed Good and leaves already-encoded state UNTOUCHED (a knowledge_gap
    grade on presented material must neither reward nor punish — the still-
    due schedule brings it back soon on its own). The exercise is never
    spent: it becomes the first real retrieval of the just-encoded content."""
    ex = store.exercises.get(campaign_id, exercise_id)
    if ex is None or ex.quality == "diagnostic":
        return
    stamp = datetime.now(timezone.utc).isoformat()
    if ex.kind in ("skill", "present"):
        campaign = store.campaigns.get(campaign_id)
        if campaign is None:
            return
        entry = next(
            (t for t in campaign.topics if t.get("path") == ex.topic_path), None
        )
        if entry is None:
            entry = {"path": ex.topic_path, "kind": "skill", "summary": ""}
            campaign.topics.append(entry)
        if not entry.get("sr"):
            entry["sr"] = scheduling.record_exposure(None, now=now)
            campaign.updated_at = stamp
            store.campaigns.save(campaign)
    elif ex.sr is None:
        ex.sr = scheduling.record_exposure(None, now=now)
        ex.updated_at = stamp
        store.exercises.save(campaign_id, ex)


def land_score(
    store,
    campaign_id: str,
    exercise_id: str,
    *,
    score: float,
    latency_seconds: Optional[float] = None,
    skip_reason: Optional[str] = None,
) -> None:
    """Advances the right memory model for one FINAL score (see module
    docstring for the lane rules). Provisional scores must never call this.
    Unknown exercises are a silent no-op."""
    ex = store.exercises.get(campaign_id, exercise_id)
    if ex is None:
        return
    if ex.quality == "diagnostic":
        # Diagnostics gather information, not memories: no SR state, and an
        # answered one retires so it never repeats (packet serves only
        # quality=="diagnostic", which now means "not yet answered").
        ex.quality = "spent"
        ex.updated_at = datetime.now(timezone.utc).isoformat()
        store.exercises.save(campaign_id, ex)
        return

    if ex.kind in ("skill", "present"):
        # present rides the skill lane (topic-scheduled, disposable) — a
        # skip verdict on one ("too_easy" = already knows it) is real
        # evidence and lands like any skill outcome (ADR 017).
        campaign = store.campaigns.get(campaign_id)
        if campaign is not None:
            entry = next(
                (t for t in campaign.topics if t.get("path") == ex.topic_path), None
            )
            if entry is None:
                entry = {"path": ex.topic_path, "kind": "skill", "summary": ""}
                campaign.topics.append(entry)
            entry["sr"] = scheduling.record_outcome(
                entry.get("sr"), score=score,
                latency_seconds=latency_seconds, skip_reason=skip_reason,
            )
            campaign.updated_at = datetime.now(timezone.utc).isoformat()
            store.campaigns.save(campaign)
        if ex.quality not in ("too_easy", "too_hard", "bad_quality"):
            ex.quality = "spent"
    else:
        ex.sr = scheduling.record_outcome(
            ex.sr, score=score, latency_seconds=latency_seconds, skip_reason=skip_reason,
        )
    ex.updated_at = datetime.now(timezone.utc).isoformat()
    store.exercises.save(campaign_id, ex)
