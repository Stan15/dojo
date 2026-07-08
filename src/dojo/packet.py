"""Daily packet construction: Tier-1 attention allocation across campaigns and
Tier-2 selection within them (blueprint §7, ADR 012; invariants I3, I8, I9).

Everything here is a pure function of store state + clock (+ seeded
tie-breaks): same state, same day → same packet. No IO beyond reads through
the store; no model involvement, ever. Every choice carries a one-sentence
plain-language reason — `dojo why` is just these strings replayed.

Non-bombardment (I3) is enforced at ONE choke point: `build_packet` clamps to
the cap before returning, and nothing else assembles practice queues.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from . import scheduling
from .schemas import Campaign, Exercise

DEFAULT_PACKET_SIZE = 5
HARD_MAX_PACKET_SIZE = 8

# Tier-1 weights (blueprint §7): visible, deterministic, configurable later.
W_DUE = 1.0
W_ATROPHY = 0.6

EXCLUDED_QUALITIES = {"archived", "too_easy", "too_hard", "bad_quality", "spent", "diagnostic"}


@dataclass
class PacketItem:
    campaign_id: str
    exercise_id: str
    reason: str  # I9: one honest sentence


@dataclass
class Packet:
    items: list[PacketItem] = field(default_factory=list)
    needs_generation: list[dict[str, Any]] = field(default_factory=list)  # skill topics due, no stock
    campaign_reasons: dict[str, str] = field(default_factory=dict)  # Tier-1 choices explained
    skipped: dict[str, int] = field(default_factory=dict)  # honest degradation counts (I10)


def _days_since_touch(campaign_id: str, store, now: datetime) -> float:
    attempts = store.attempts.list(campaign_id)
    if not attempts:
        return 7.0  # never practiced counts as a week of atrophy — new things want starting
    last = max(a.created_at for a in attempts)
    return max(0.0, (now - datetime.fromisoformat(last)).total_seconds() / 86400)


def _topic_emphasis(campaign: Campaign) -> dict[str, float]:
    """Learner-set intra-campaign boosts ("this topic more often"): emphasis > 1
    accelerates a topic's due cycle and wins composition ties."""
    return {
        t["path"]: float(t.get("emphasis", 1.0))
        for t in (campaign.topics or [])
        if t.get("path")
    }


def _emphasized_due(sr, emphasis: float, now: datetime) -> bool:
    """An emphasis of 2 makes an item due in half its scheduled interval."""
    if emphasis <= 1.0 or not sr or not sr.get("last_review"):
        return scheduling.is_due(sr, now)
    last = datetime.fromisoformat(sr["last_review"])
    scheduled = scheduling.due_at(sr)
    effective = last + (scheduled - last) / emphasis
    return effective <= now


def _due_exercises(store, campaign: Campaign, now: datetime) -> list[Exercise]:
    emphasis = _topic_emphasis(campaign)
    due = []
    for ex in store.exercises.list(campaign.id):
        if ex.quality in EXCLUDED_QUALITIES:
            continue
        if _emphasized_due(ex.sr, emphasis.get(ex.topic_path, 1.0), now):
            due.append(ex)
    return sorted(due, key=lambda e: (-emphasis.get(e.topic_path, 1.0), e.id))


def campaign_priority(
    store, campaign: Campaign, now: datetime
) -> tuple[float, str, list[Exercise]]:
    """Tier-1 score: campaigns don't forget, learners under-attend them —
    urgency-weighted fairness, not memory math (ADR 012)."""
    due = _due_exercises(store, campaign, now)
    days = _days_since_touch(campaign.id, store, now)
    due_pressure = min(len(due) / 5.0, 1.0)
    atrophy = min(days / 7.0, 1.0)
    score = W_DUE * due_pressure + W_ATROPHY * atrophy
    boost = float(campaign.strategy_profile.get("priority_weight", 1.0))
    score *= boost
    reason = (
        f"{campaign.name}: {len(due)} due, untouched "
        f"{'today' if days < 1 else f'{days:.0f}d'}"
    )
    if boost != 1.0:
        reason += f", boosted ×{boost:g} by you"
    return score, reason, due


def _compose_for_campaign(
    due: list[Exercise], slots: int, now: datetime, rng: random.Random
) -> list[tuple[Exercise, str]]:
    """Tier-2 mix per pedagogy-foundation: weakest memory first, one easy
    maintenance win, one never-practiced frontier item when available."""
    if not due or slots <= 0:
        return []
    fresh = [e for e in due if e.sr is None]
    seen = [e for e in due if e.sr is not None]
    by_weakness = sorted(
        seen, key=lambda e: (scheduling.retrievability(e.sr, now), e.id)
    )

    picks: list[tuple[Exercise, str]] = []
    if by_weakness:
        weakest = by_weakness.pop(0)
        r = scheduling.retrievability(weakest.sr, now)
        picks.append((weakest, f"weakest memory here (~{r:.0%} recall odds)"))
    if by_weakness and len(picks) < slots:
        strongest = by_weakness.pop(-1)
        picks.append((strongest, "an easy maintenance win to keep it warm"))
    if fresh and len(picks) < slots:
        frontier = fresh.pop(rng.randrange(len(fresh)))
        picks.append((frontier, "new ground: never practiced yet"))
    pool = by_weakness + fresh
    while pool and len(picks) < slots:
        nxt = pool.pop(0)
        why = "due for review" if nxt.sr is not None else "new ground: never practiced yet"
        picks.append((nxt, why))
    return picks[:slots]


def _skill_topics_needing_stock(store, campaign: Campaign, due: list[Exercise], now: datetime) -> list[dict[str, Any]]:
    """Skill topics whose memory is due but which have no unspent novel item in
    stock (ADR 012: skill items are disposable; due topic + empty stock =
    generation request)."""
    stocked = {ex.topic_path for ex in due if ex.kind == "skill"}
    needs = []
    for topic in campaign.topics or []:
        if topic.get("kind") != "skill":
            continue
        if not _emphasized_due(topic.get("sr"), float(topic.get("emphasis", 1.0)), now):
            continue
        if topic["path"] in stocked:
            continue
        needs.append({
            "campaign_id": campaign.id,
            "topic_path": topic["path"],
            "reason": "skill due for fresh practice, no novel exercise in stock",
        })
    return needs


def build_packet(
    store,
    now: datetime,
    *,
    size: Optional[int] = None,
    seed: Optional[int] = None,
) -> Packet:
    """The single assembler of daily practice (I3 choke point)."""
    configured = size or int(store.configs.get_value("daily.packet_size", DEFAULT_PACKET_SIZE))
    cap = max(1, min(configured, HARD_MAX_PACKET_SIZE))
    rng = random.Random(seed if seed is not None else now.strftime("%Y%m%d"))

    packet = Packet()
    ranked = []
    for campaign in store.campaigns.list():
        if campaign.status != "active":
            continue
        score, reason, due = campaign_priority(store, campaign, now)
        ranked.append((score, campaign.id, reason, campaign, due))
        packet.needs_generation.extend(
            _skill_topics_needing_stock(store, campaign, due, now)
        )
    ranked.sort(key=lambda t: (-t[0], t[1]))

    with_due = [r for r in ranked if r[4]]
    for _, _, reason, campaign, _ in ranked:
        packet.campaign_reasons[campaign.id] = reason

    if with_due:
        # Interleave: top campaign gets the larger share, every due campaign
        # gets at least one slot while slots last (desirable difficulty).
        shares = _allocate_slots(cap, len(with_due))
        for (share, (_, _, _, campaign, due)) in zip(shares, with_due):
            for ex, why in _compose_for_campaign(due, share, now, rng):
                packet.items.append(PacketItem(
                    campaign_id=campaign.id, exercise_id=ex.id,
                    reason=f"{why} · {packet.campaign_reasons[campaign.id]}",
                ))

    overflow = sum(len(r[4]) for r in with_due) - len(packet.items)
    if overflow > 0:
        packet.skipped["due_beyond_cap"] = overflow

    packet.items = packet.items[:cap]  # the clamp that makes I3 unbreakable
    return packet


def _allocate_slots(cap: int, campaigns: int) -> list[int]:
    """Front-loaded fair shares: e.g. cap 5 over 3 campaigns → [3, 1, 1]."""
    if campaigns <= 0:
        return []
    campaigns = min(campaigns, cap)
    base = [1] * campaigns
    remaining = cap - campaigns
    base[0] += remaining
    return base
