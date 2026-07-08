"""Scheduling boundary tests (ADR 014, I8).

The wrapper is dojo's correctness surface over py-fsrs: the band→rating
mapping, determinism under an injected clock, serialization through plain
dicts (frontmatter-safe), and the semantics packet-building relies on
(new = due, intervals grow with success, lapses come back fast).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import yaml
from fsrs import Rating

from dojo import scheduling

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


class TestRatingMapping:
    """ADR 014's table, pinned exactly."""

    def test_bands(self):
        assert scheduling.rating_for(0.0) == Rating.Again
        assert scheduling.rating_for(0.3) == Rating.Again
        assert scheduling.rating_for(0.7) == Rating.Hard
        assert scheduling.rating_for(1.0, latency_seconds=60.0) == Rating.Good

    def test_fast_perfect_answer_earns_easy(self):
        assert scheduling.rating_for(1.0, latency_seconds=5.0) == Rating.Easy
        assert scheduling.rating_for(1.0, latency_seconds=None) == Rating.Good

    def test_skips_override_score(self):
        assert scheduling.rating_for(0.0, skip_reason="too_easy") == Rating.Easy
        assert scheduling.rating_for(1.0, skip_reason="forgot") == Rating.Again


class TestMemoryModel:
    def test_new_state_is_due_immediately(self):
        sr = scheduling.new_state(NOW)
        assert scheduling.is_due(sr, NOW)

    def test_no_state_means_due(self):
        assert scheduling.is_due(None, NOW)

    def test_success_grows_the_interval(self):
        sr = scheduling.new_state(NOW)
        now = NOW
        previous_gap = timedelta(0)
        for _ in range(4):
            sr = scheduling.record_outcome(sr, score=1.0, latency_seconds=30.0, now=now)
            gap = scheduling.due_at(sr) - now
            assert gap >= previous_gap, "intervals must not shrink under repeated success"
            previous_gap = gap
            now = scheduling.due_at(sr)
        assert previous_gap > timedelta(days=1), "sustained success reaches multi-day spacing"

    def test_lapse_brings_the_item_back_fast(self):
        sr = scheduling.new_state(NOW)
        now = NOW
        for _ in range(4):
            sr = scheduling.record_outcome(sr, score=1.0, latency_seconds=30.0, now=now)
            now = scheduling.due_at(sr)
        sr = scheduling.record_outcome(sr, score=0.0, now=now)
        assert scheduling.due_at(sr) - now < timedelta(days=1), "a lapse re-queues quickly"

    def test_fuzzing_is_disabled_at_the_boundary(self):
        """py-fsrs fuzzes intervals by default via GLOBAL random — nondeterminism
        that broke a packet test as a flake. I8 requires it off, forever."""
        import random
        outs = []
        for salt in range(3):
            random.seed(salt)  # global seed must be irrelevant
            sr = scheduling.new_state(NOW)
            for d in (0, 1, 3):
                sr = scheduling.record_outcome(sr, score=1.0, latency_seconds=30.0,
                                               now=NOW + timedelta(days=d))
            outs.append(sr["due"])
        assert len(set(outs)) == 1, "schedule depends on global random state (fuzzing on?)"

    def test_deterministic_under_injected_clock(self):
        a = scheduling.record_outcome(scheduling.new_state(NOW), score=0.7, now=NOW)
        b = scheduling.record_outcome(scheduling.new_state(NOW), score=0.7, now=NOW)
        a.pop("card_id"), b.pop("card_id")  # identity differs; memory math may not
        assert a == b

    def test_state_survives_yaml_frontmatter_round_trip(self):
        sr = scheduling.record_outcome(scheduling.new_state(NOW), score=1.0,
                                       latency_seconds=20.0, now=NOW)
        thawed = yaml.safe_load(yaml.safe_dump(sr))
        again = scheduling.record_outcome(thawed, score=1.0, latency_seconds=20.0,
                                          now=NOW + timedelta(days=1))
        assert scheduling.due_at(again) > scheduling.due_at(sr)

    def test_retrievability_decays_and_is_honest_about_unknowns(self):
        assert scheduling.retrievability(None, NOW) == 0.0
        sr = scheduling.record_outcome(scheduling.new_state(NOW), score=1.0,
                                       latency_seconds=30.0, now=NOW)
        soon = scheduling.retrievability(sr, NOW + timedelta(hours=1))
        later = scheduling.retrievability(sr, NOW + timedelta(days=30))
        assert 0.0 < later < soon <= 1.0
