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


def land_score(
    store,
    campaign_id: str,
    exercise_id: str,
    *,
    score: float,
    latency_seconds: Optional[float] = None,
    skip_reason: Optional[str] = None,
) -> None:
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

    if ex.kind == "skill":
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
