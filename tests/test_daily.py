"""dojo daily / why / boost tests — including the offline floor (I4): with no
AI fulfiller anywhere, the daily ritual still works on due recall items, and
everything missing is an emitted task plus an honest count, never a fake."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from dojo import scheduling
from dojo.api import DojoAPI
from dojo.cli import main
from dojo.schemas import Exercise


@pytest.fixture(autouse=True)
def no_git():
    with patch("dojo.store.engine.init_git"), patch("dojo.store.engine.commit_git"):
        yield


def run(capsys, *argv: str) -> tuple[int, dict]:
    rc = main(list(argv))
    return rc, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def seed(api: DojoAPI) -> str:
    cid = api.create_campaign(name="French", topic_path="french", mission="NCLC 7.")["id"]
    now = datetime.now(timezone.utc)
    lapsed = scheduling.record_outcome(
        scheduling.new_state(now - timedelta(days=5)), score=0.0, now=now - timedelta(days=4),
    )
    api.store.exercises.save(cid, Exercise(
        id="ex_lapsed", topic_path="french.vocab", difficulty="beginner",
        answer="chien", prompt="dog = ?", sr=lapsed,
    ))
    api.store.exercises.save(cid, Exercise(
        id="ex_fresh", topic_path="french.vocab", difficulty="beginner",
        answer="chat", prompt="cat = ?",
    ))
    camp = api.store.campaigns.get(cid)
    camp.topics = [{
        "path": "french.oral", "kind": "skill",
        "sr": scheduling.new_state(now - timedelta(days=1)),  # due skill topic, no stock
    }]
    api.store.campaigns.save(camp)
    return cid


class TestOfflineFloor:
    def test_daily_works_with_zero_ai_available(self, tmp_path: Path):
        """I4: recall practice proceeds; the missing skill stock is an emitted
        task and a visible line item — degradation is honest, never silent."""
        api = DojoAPI(tmp_path)
        seed(api)
        res = api.daily()

        assert res["is_new"] and res["session"] is not None
        ids = set(res["session"]["exercise_ids"])
        assert {"ex_lapsed", "ex_fresh"} <= ids, "due recall items always practicable"
        assert len(res["tasks"]) == 1, "due skill topic without stock → generation task"

        # the session is fully drivable offline, end to end
        session_id = res["session"]["id"]
        for _ in range(len(ids)):
            prompt_info = api.reveal_prompt(session_id=session_id)
            ans = api.submit_answer(
                user_answer="chien" if "dog" in prompt_info["prompt"] else "chat",
                session_id=session_id,
            )
            assert ans["grader"] == "exact" and not ans["pending_grade"]

    def test_empty_schedule_is_a_day_off_not_an_error(self, tmp_path: Path):
        api = DojoAPI(tmp_path)
        cid = api.create_campaign(name="C", topic_path="c", mission="m")["id"]
        # one well-scheduled (not due) item, nothing else
        now = datetime.now(timezone.utc)
        sr = scheduling.new_state(now - timedelta(days=3))
        for d in (3, 2):
            sr = scheduling.record_outcome(sr, score=1.0, latency_seconds=5.0,
                                           now=now - timedelta(days=d))
        api.store.exercises.save(cid, Exercise(
            id="ex_ok", topic_path="c.t", difficulty="beginner", answer="x", prompt="?",
            sr=sr,
        ))
        res = api.daily()
        assert res["session"] is None and res["tasks"] == []
        assert "day off" in res["next"], "an empty schedule is stated proudly, not apologized for"


class TestDailyLoop:
    def test_daily_resumes_same_session_within_day(self, tmp_path: Path):
        api = DojoAPI(tmp_path)
        seed(api)
        first = api.daily()
        again = api.daily()
        assert not again["is_new"]
        assert again["session"]["id"] == first["session"]["id"]

    def test_why_replays_reasons(self, tmp_path: Path, capsys):
        api = DojoAPI(tmp_path)
        seed(api)
        api.daily()
        rc, data = run(capsys, "--db", str(tmp_path), "why")
        assert rc == 0
        reasons = {i["exercise_id"]: i["reason"] for i in data["items"]}
        assert "weakest memory" in reasons["ex_lapsed"]
        assert "never practiced" in reasons["ex_fresh"]
        assert data["campaigns"], "Tier-1 ranking is explained too"


class TestBoostCommands:
    def test_campaign_boost_and_topic_boost_roundtrip(self, tmp_path: Path, capsys):
        api = DojoAPI(tmp_path)
        cid = seed(api)

        rc, data = run(capsys, "--db", str(tmp_path), "campaign", "boost", cid, "2.5")
        assert rc == 0 and "x2.5 priority" in data["effect"]
        assert api.store.campaigns.get(cid).strategy_profile["priority_weight"] == 2.5

        rc, data = run(capsys, "--db", str(tmp_path), "campaign", "topic-boost",
                       cid, "french.vocab", "3.0")
        assert rc == 0 and "3 faster" in data["effect"].replace("x3", "3")
        camp = api.store.campaigns.get(cid)
        entry = next(t for t in camp.topics if t["path"] == "french.vocab")
        assert entry["emphasis"] == 3.0

        # and the boost is visible in the next packet's reasons (I9)
        api.daily(reset=True)
        why = api.why()
        assert any("boosted" in r for r in why["campaigns"].values())


class TestColdStartAndPhaseGating:
    """E2E finding 2026-07-08: a fresh plan emitted 5 generation tasks at once.
    Now: evidence-free campaigns calibrate first (ONE diagnostic task), stock
    requests are gated to the active phase, and daily emits at most 2 AI tasks
    per run with the rest counted honestly."""

    def _planned_campaign(self, api: DojoAPI) -> str:
        from dojo.schemas import AttackPlanPhase, CriteriaEntry
        cid = api.create_campaign(name="Git Arch", topic_path="git",
                                  mission="Do code archaeology confidently.")["id"]
        camp = api.store.campaigns.get(cid)
        camp.topics = [
            {"path": "git.objects", "kind": "recall", "summary": ""},
            {"path": "git.log_queries", "kind": "skill", "summary": ""},
            {"path": "git.blame", "kind": "skill", "summary": ""},
            {"path": "git.bisect", "kind": "skill", "summary": ""},
            {"path": "git.merges", "kind": "skill", "summary": ""},
        ]
        camp.attack_plan = [
            AttackPlanPhase(phase=1, topics=["git.objects"],
                            criteria=CriteriaEntry(min_attempts=5, min_accuracy=0.0),
                            focus="calibration"),
            AttackPlanPhase(phase=2, topics=["git.log_queries", "git.blame"],
                            criteria=CriteriaEntry(min_attempts=10, min_accuracy=0.7)),
        ]
        camp.active_phase_index = 0
        api.store.campaigns.save(camp)
        return cid

    def test_cold_campaign_gets_one_diagnostic_task(self, tmp_path: Path):
        api = DojoAPI(tmp_path)
        self._planned_campaign(api)
        res = api.daily()
        assert res["session"] is None
        assert len(res["tasks"]) == 1, "calibrate first — never a wall of generation tasks"
        task = api.store.tasks.get(res["tasks"][0]["id"])
        assert task.kind == "exercise.diagnostic"
        assert task.context["topic_path"] == "git.objects", "phase 1's topic, not the whole tree"

    def test_warm_campaign_stock_requests_are_phase_gated_and_capped(self, tmp_path: Path):
        from dojo.schemas import Attempt
        api = DojoAPI(tmp_path)
        cid = self._planned_campaign(api)
        camp = api.store.campaigns.get(cid)
        camp.active_phase_index = 1  # phase 2 active: log_queries + blame only
        api.store.campaigns.save(camp)
        api.store.attempts.save(cid, Attempt(
            id="att_1", session_id="s1", exercise_id="ex_old", campaign_id=cid,
            score=1.0, latency_seconds=10.0, user_answer="x",
        ))
        res = api.daily()
        emitted = [api.store.tasks.get(t["id"]).context["topic_path"] for t in res["tasks"]]
        assert set(emitted) <= {"git.log_queries", "git.blame"}, (
            f"later-phase topics (bisect/merges) must not request stock yet: {emitted}"
        )
        assert len(res["tasks"]) <= 2, "token frugality: at most 2 AI tasks per daily"
