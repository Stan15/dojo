"""ADR 017 §6 — the care-exit: topic retirement + the lifetime trend digest.

Pins: reflection may retire topics only through the validated channel
(registered, not already retired, cited evidence shown, capped per run);
a retired topic stops producing dues everywhere (packet, replenishment,
debt guard, weakest-topic) but is counted honestly (stats, announce-once);
the learner door is immediate and reversible; the trend digest gives
reflection lifetime eyes and never counts encodings toward mastery.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from dojo import scheduling
from dojo.api import DojoAPI
from dojo.packet import build_packet
from dojo.schemas import Attempt, Exercise
from dojo.tasks import compiler, service

CAMP_ID = "memory"
NOW = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_git():
    with patch("dojo.store.engine.init_git"), patch("dojo.store.engine.commit_git"):
        yield


@pytest.fixture
def api(tmp_path: Path) -> DojoAPI:
    a = DojoAPI(tmp_path)
    a.create_campaign(name="memory", topic_path="memory", mission="Train recall.")
    camp = a.store.campaigns.get(CAMP_ID)
    camp.topics = [
        {"path": "memory.keys", "kind": "skill", "summary": "",
         "sr": scheduling.new_state(NOW - timedelta(days=2))},
        {"path": "memory.rules", "kind": "recall", "summary": ""},
    ]
    a.store.campaigns.save(camp)
    # A due recall exercise on the retirable topic + one unreflected attempt
    # (reflection needs evidence to trigger a task).
    due_sr = scheduling.record_outcome(
        scheduling.new_state(NOW - timedelta(days=9)), score=1.0, now=NOW - timedelta(days=8))
    a.store.exercises.save(CAMP_ID, Exercise(
        id="ex_k", topic_path="memory.keys", difficulty="beginner", kind="recall",
        answer="cat, tree, turmoil, hat", prompt="Recall the golden apple key.", sr=due_sr,
    ))
    a.store.attempts.save(CAMP_ID, Attempt(
        id="att_1", session_id="s", exercise_id="ex_k", campaign_id=CAMP_ID,
        score=1.0, grader="ai", latency_seconds=10.0,
        created_at=(NOW - timedelta(days=8)).isoformat(),
        prompt="Recall the golden apple key.", user_answer="cat tree turmoil hat",
    ))
    return a


def _reflect(api: DojoAPI, payload: dict):
    compiled = compiler.compile_reflect(api.store, api.store.campaigns.get(CAMP_ID))
    task_id = service.emit(api.store, compiled).id
    base = {"insight_updates": [], "strategy": None, "plan_revision": None,
            "questions": [], "journal": "care-exit check"}
    return service.submit(api.store, task_id, json.dumps({**base, **payload}))


class TestReflectRetirementChannel:
    def test_valid_retirement_applies_announced_once(self, api):
        outcome = _reflect(api, {"topic_retirements": [
            {"path": "memory.keys", "reason": "fluent for months, learner moved on",
             "evidence": ["att_1"]},
        ]})
        assert outcome.ok, outcome.errors
        assert outcome.applied["topics_retired"] == ["memory.keys"]
        camp = api.store.campaigns.get(CAMP_ID)
        entry = next(t for t in camp.topics if t["path"] == "memory.keys")
        assert entry["retired"] is True
        notes, _ = api._ownership_notices()
        assert any(n.get("topic_retired") == "memory.keys" for n in notes)
        notes_again, _ = api._ownership_notices()
        assert not any(n.get("topic_retired") for n in notes_again), "announced exactly once"

    def test_unknown_topic_rejected_state_unchanged(self, api):
        outcome = _reflect(api, {"topic_retirements": [
            {"path": "memory.ghost", "reason": "nope", "evidence": []},
        ]})
        assert not outcome.ok
        assert any("unregistered" in e for e in outcome.errors)
        camp = api.store.campaigns.get(CAMP_ID)
        assert not any(t.get("retired") for t in camp.topics)

    def test_already_retired_rejected(self, api):
        api.topic_retire("memory.keys")
        outcome = _reflect(api, {"topic_retirements": [
            {"path": "memory.keys", "reason": "again", "evidence": []},
        ]})
        assert not outcome.ok and any("already retired" in e for e in outcome.errors)

    def test_over_cap_rejected_by_schema(self, api):
        outcome = _reflect(api, {"topic_retirements": [
            {"path": f"memory.t{i}", "reason": "r", "evidence": []} for i in range(3)
        ]})
        assert not outcome.ok


class TestRetiredIsExcludedEverywhere:
    def test_no_dues_no_replenishment(self, api):
        api.topic_retire("memory.keys", because="moved on")
        pkt = build_packet(api.store, NOW, size=5)
        assert not any(i.exercise_id == "ex_k" for i in pkt.items)
        assert not any(n["topic_path"] == "memory.keys" for n in pkt.needs_generation)

    def test_debt_guard_and_weakest_topic_skip_retired(self, api):
        before, _ = api._review_load_7d(NOW)
        api.topic_retire("memory.keys")
        after, _ = api._review_load_7d(NOW)
        assert after == before - 2, "one due exercise + one due skill topic left the debt"
        assert api._weakest_topic() is None, "the only scored topic is retired"

    def test_stats_count_retired_honestly(self, api):
        api.topic_retire("memory.keys")
        row = next(c for c in api.stats(now=NOW)["campaigns"] if c["campaign_id"] == CAMP_ID)
        assert row["retired_topics"] == 1


class TestLearnerDoor:
    def test_retire_and_revive_round_trip(self, api):
        res = api.topic_retire("memory.keys", because="I stopped caring")
        assert res["ok"] and "revive" in res["next"]
        entry = next(t for t in api.store.campaigns.get(CAMP_ID).topics
                     if t["path"] == "memory.keys")
        assert entry["retired_reason"] == "I stopped caring"
        api.topic_revive("memory.keys")
        entry = next(t for t in api.store.campaigns.get(CAMP_ID).topics
                     if t["path"] == "memory.keys")
        assert "retired" not in entry
        assert entry.get("sr"), "the memory state survived the round trip"

    def test_unknown_topic_raises(self, api):
        with pytest.raises(ValueError, match="not registered"):
            api.topic_retire("memory.ghost")


class TestTrendDigest:
    def test_lifetime_lines_with_trend_and_miss_age(self, api):
        for i, (score, days) in enumerate([(0.3, 7), (0.7, 5), (1.0, 3), (1.0, 1)]):
            api.store.attempts.save(CAMP_ID, Attempt(
                id=f"att_t{i}", session_id="s", exercise_id="ex_k", campaign_id=CAMP_ID,
                score=score, grader="ai", latency_seconds=9.0,
                created_at=(NOW - timedelta(days=days)).isoformat(),
                prompt="p", user_answer="a",
            ))
        rows = compiler.trend_rows(api.store, api.store.campaigns.get(CAMP_ID))
        line = next(r for r in rows.splitlines() if r.startswith("memory.keys"))
        assert "5 graded" in line and "acc" in line and "last miss" in line
        assert "memory.rules · no graded practice yet" in rows

    def test_exposures_never_count_toward_trends(self, api):
        api.store.attempts.save(CAMP_ID, Attempt(
            id="att_e", session_id="s", exercise_id="ex_k", campaign_id=CAMP_ID,
            score=0.0, grader="exposure", reflected=True, latency_seconds=5.0,
            created_at=NOW.isoformat(), prompt="p", user_answer="",
        ))
        rows = compiler.trend_rows(api.store, api.store.campaigns.get(CAMP_ID))
        line = next(r for r in rows.splitlines() if r.startswith("memory.keys"))
        assert "1 graded" in line, "the exposure was not counted"

    def test_retired_topics_labeled(self, api):
        api.topic_retire("memory.keys", because="moved on")
        rows = compiler.trend_rows(api.store, api.store.campaigns.get(CAMP_ID))
        assert "memory.keys · RETIRED (moved on)" in rows
