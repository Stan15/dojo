"""Packet builder tests — the I3/I8 correctness pins (blueprint §7).

The property tests run the builder over seeded-random store states: the cap
must be unbreakable, identical state+date must yield identical packets, and
excluded items must never leak in. The boost tests pin the owner's two
priority knobs: topic emphasis (intra-campaign) and campaign priority_weight
(cross-campaign) — and that both show up honestly in the reasons (I9).
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dojo import packet, scheduling
from dojo.schemas import Attempt, Campaign, Exercise
from dojo.store import DojoStore

NOW = datetime(2026, 7, 7, 9, 0, tzinfo=timezone.utc)


def make_store(tmp_path: Path, name: str = "s") -> DojoStore:
    return DojoStore(tmp_path / name)


def add_campaign(store: DojoStore, cid: str, **kwargs) -> Campaign:
    camp = Campaign(id=cid, name=cid, mission=f"Master {cid}.", **kwargs)
    store.campaigns.save(camp)
    return camp


def add_exercise(store: DojoStore, cid: str, ex_id: str, **kwargs) -> Exercise:
    defaults = dict(topic_path=f"{cid}.core", difficulty="beginner", prompt=f"Q {ex_id}")
    defaults.update(kwargs)
    ex = Exercise(id=ex_id, **defaults)
    store.exercises.save(cid, ex)
    return ex


class TestProperties:
    """Randomized store states, seeded: the invariants that may never break."""

    def _random_store(self, tmp_path: Path, rng: random.Random, idx: int) -> DojoStore:
        store = make_store(tmp_path, f"rand{idx}")
        for c in range(rng.randint(1, 4)):
            cid = f"camp{c}"
            add_campaign(store, cid, strategy_profile={
                "priority_weight": rng.choice([0.5, 1.0, 1.0, 2.0]),
            })
            for e in range(rng.randint(0, 12)):
                quality = rng.choice(
                    ["reviewed"] * 6 + ["archived", "too_easy", "spent", "diagnostic"]
                )
                sr = None
                if rng.random() < 0.6:
                    sr = scheduling.new_state(NOW - timedelta(days=rng.randint(0, 30)))
                    if rng.random() < 0.7:
                        sr = scheduling.record_outcome(
                            sr, score=rng.choice([0.0, 0.3, 0.7, 1.0]),
                            latency_seconds=rng.uniform(3, 90),
                            now=NOW - timedelta(days=rng.randint(0, 20)),
                        )
                add_exercise(
                    store, cid, f"ex_{c}_{e}",
                    kind=rng.choice(["recall", "recall", "skill"]),
                    quality=quality, sr=sr,
                )
        return store

    @pytest.mark.parametrize("case", range(8))
    def test_cap_determinism_and_exclusions(self, tmp_path: Path, case: int):
        rng = random.Random(20260707 + case)
        store = self._random_store(tmp_path, rng, case)

        first = packet.build_packet(store, NOW)
        second = packet.build_packet(store, NOW)

        # I3: the cap is unbreakable
        assert len(first.items) <= packet.HARD_MAX_PACKET_SIZE
        assert len(first.items) <= packet.DEFAULT_PACKET_SIZE

        # I8: same state, same day → same packet
        assert [(i.campaign_id, i.exercise_id) for i in first.items] == \
               [(i.campaign_id, i.exercise_id) for i in second.items]

        # excluded qualities never leak in
        for item in first.items:
            ex = store.exercises.get(item.campaign_id, item.exercise_id)
            assert ex.quality not in packet.EXCLUDED_QUALITIES

        # I9: every choice carries a reason
        assert all(item.reason for item in first.items)

    def test_interleaves_when_multiple_campaigns_have_due(self, tmp_path: Path):
        store = make_store(tmp_path)
        for cid in ("alpha", "beta"):
            add_campaign(store, cid)
            for i in range(4):
                add_exercise(store, cid, f"{cid}_ex{i}")
        built = packet.build_packet(store, NOW)
        campaigns_in_packet = {i.campaign_id for i in built.items}
        assert campaigns_in_packet == {"alpha", "beta"}, "desirable difficulty: interleave"

    def test_overflow_is_counted_not_hidden(self, tmp_path: Path):
        store = make_store(tmp_path)
        add_campaign(store, "big")
        for i in range(12):
            add_exercise(store, "big", f"ex{i}")
        built = packet.build_packet(store, NOW)
        assert len(built.items) == packet.DEFAULT_PACKET_SIZE
        assert built.skipped["due_beyond_cap"] == 12 - len(built.items)


class TestComposition:
    def test_mix_prefers_weakest_then_maintenance_then_frontier(self, tmp_path: Path):
        store = make_store(tmp_path)
        add_campaign(store, "c")
        weak_sr = scheduling.record_outcome(
            scheduling.new_state(NOW - timedelta(days=10)), score=0.0,
            now=NOW - timedelta(days=9),
        )
        strong_sr = scheduling.record_outcome(
            scheduling.new_state(NOW - timedelta(days=10)), score=1.0,
            latency_seconds=5.0, now=NOW - timedelta(days=8),
        )
        add_exercise(store, "c", "weak", sr=weak_sr)
        add_exercise(store, "c", "strong", sr=strong_sr)
        add_exercise(store, "c", "fresh")  # never practiced

        built = packet.build_packet(store, NOW)
        reasons = {i.exercise_id: i.reason for i in built.items}
        assert "weakest memory" in reasons["weak"]
        assert "maintenance" in reasons["strong"]
        assert "never practiced" in reasons["fresh"]


class TestBoosts:
    """The owner's two priority knobs, disambiguated (2026-07-07 directive)."""

    def test_campaign_boost_reorders_tier1_and_says_so(self, tmp_path: Path):
        store = make_store(tmp_path)
        add_campaign(store, "quiet", strategy_profile={"priority_weight": 3.0})
        add_exercise(store, "quiet", "q0")
        add_campaign(store, "busy")
        for i in range(5):
            add_exercise(store, "busy", f"b{i}")
        # busy has more due pressure, but quiet is boosted ×3
        built = packet.build_packet(store, NOW)
        assert built.items[0].campaign_id == "quiet"
        assert "boosted ×3 by you" in built.campaign_reasons["quiet"]

    def test_topic_emphasis_accelerates_the_due_cycle(self, tmp_path: Path):
        store = make_store(tmp_path)
        camp = add_campaign(store, "c")
        # a well-known item scheduled ~days out: not due normally
        sr = scheduling.new_state(NOW - timedelta(days=10))
        for d in (10, 8, 5, 2):
            sr = scheduling.record_outcome(
                sr, score=1.0, latency_seconds=5.0, now=NOW - timedelta(days=d),
            )
        assert not scheduling.is_due(sr, NOW), "test setup: item must not be due yet"
        add_exercise(store, "c", "known", topic_path="c.hot", sr=sr)

        assert packet.build_packet(store, NOW).items == [], "not due without emphasis"

        # interval ≈ 70d, elapsed 2d: ×8 is not enough, ×40 is — both pinned
        camp.topics = [{"path": "c.hot", "kind": "recall", "emphasis": 8.0}]
        store.campaigns.save(camp)
        assert packet.build_packet(store, NOW).items == [], (
            "moderate emphasis accelerates but does not force-surface everything"
        )

        camp.topics = [{"path": "c.hot", "kind": "recall", "emphasis": 40.0}]
        store.campaigns.save(camp)
        built = packet.build_packet(store, NOW)
        assert [i.exercise_id for i in built.items] == ["known"], (
            "emphasis shrinks the effective interval, surfacing the topic sooner"
        )

    def test_emphasized_skill_topic_requests_generation_sooner(self, tmp_path: Path):
        store = make_store(tmp_path)
        camp = add_campaign(store, "c")
        # warm campaign: calibration-first only applies to evidence-free ones
        store.attempts.save("c", Attempt(
            id="att_w", session_id="s1", exercise_id="ex_gone", campaign_id="c",
            score=1.0, latency_seconds=10.0, user_answer="x",
        ))
        sr = scheduling.record_outcome(
            scheduling.new_state(NOW - timedelta(days=6)), score=1.0,
            latency_seconds=5.0, now=NOW - timedelta(days=6),
        )
        camp.topics = [{"path": "c.skill", "kind": "skill", "sr": sr}]
        store.campaigns.save(camp)
        if packet.build_packet(store, NOW).needs_generation:
            # already due even unboosted — tighten setup instead of a vacuous pass
            raise AssertionError("test setup: skill topic must not be due unboosted")

        camp.topics[0]["emphasis"] = 10.0
        store.campaigns.save(camp)
        needs = packet.build_packet(store, NOW).needs_generation
        assert needs and needs[0]["topic_path"] == "c.skill"
