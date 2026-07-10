"""ADR 017 units c+d — the `present` move and the practice-history window.

Pins: present items land through generation (answer required, rubric not),
serve as study cards (reveal carries the material; any acknowledgment
submits; never graded; exposure lands on the topic; the card is spent),
respect the per-packet encoding cap (short packet, never backfilled,
counted honestly), and the generate payload's RECENT section carries the
topic's practice arc — presentations near-verbatim with an
awaiting-first-recall flag that clears once a graded attempt lands.
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
from dojo.schemas import Attempt, Campaign, Exercise, PracticeSession
from dojo.store import DojoStore
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
    camp.id = CAMP_ID  # create_campaign slugs the name; pin the id we use
    camp.topics = [{"path": "memory.keys", "kind": "skill", "summary": ""}]
    a.store.campaigns.save(camp)
    return a


def _present_ex(**over) -> Exercise:
    base = dict(
        id="ex_p", topic_path="memory.keys", difficulty="intermediate",
        kind="present", quality="auto_accepted",
        answer="the golden apple key: cat, tree, turmoil, hat",
        prompt="Memorize the golden apple key — you will recall it later.",
    )
    base.update(over)
    return Exercise(**base)


class TestPresentGeneration:
    def _emit(self, store: DojoStore) -> str:
        camp = store.campaigns.get(CAMP_ID)
        compiled = compiler.compile_generate(
            store, camp, topic_path="memory.keys", n_items=1, difficulty="intermediate",
        )
        compiled.context["auto_promote"] = True
        return service.emit(store, compiled).id

    def test_present_item_lands_without_rubric(self, api):
        task_id = self._emit(api.store)
        outcome = service.submit(api.store, task_id, json.dumps({"items": [{
            "prompt": "Memorize the golden apple key.",
            "answer": "cat, tree, turmoil, hat", "rubric": None, "skill": "present",
        }], "note": None}))
        assert outcome.ok, outcome.errors
        ex = api.store.exercises.get(CAMP_ID, outcome.applied["exercises"][0])
        assert ex.kind == "present"

    def test_present_without_answer_rejected(self, api):
        task_id = self._emit(api.store)
        outcome = service.submit(api.store, task_id, json.dumps({"items": [{
            "prompt": "Memorize the key.", "answer": None, "rubric": None, "skill": "present",
        }], "note": None}))
        assert not outcome.ok
        assert any("presentation" in e for e in outcome.errors)


class TestPresentServing:
    def _serve(self, api: DojoAPI) -> dict:
        api.store.exercises.save(CAMP_ID, _present_ex())
        api.store.sessions.save_active(PracticeSession(id="sess_t", exercise_ids=["ex_p"]))
        return api.reveal_prompt()

    def test_reveal_carries_the_material(self, api):
        info = self._serve(api)
        assert info["present"] is True
        assert "golden apple key" in info["material"]

    def test_confirm_encodes_spends_and_never_grades(self, api):
        self._serve(api)
        res = api.submit_answer(user_answer="")
        assert res["grader"] == "exposure" and not res["pending_grade"]
        att = api.store.attempts.get(CAMP_ID, res["attempt_id"])
        assert att.reflected is True
        ex = api.store.exercises.get(CAMP_ID, "ex_p")
        assert ex.quality == "spent", "a presentation is consumed by viewing"
        topic = next(t for t in api.store.campaigns.get(CAMP_ID).topics
                     if t["path"] == "memory.keys")
        assert topic.get("sr"), "encoding initialized the topic schedule"
        assert topic["sr"]["difficulty"] < 7, "fixed Good, not a lapse"

    def test_too_easy_skip_lands_real_evidence(self, api):
        self._serve(api)
        res = api.skip_active_exercise("too_easy")
        assert res is not None
        topic = next(t for t in api.store.campaigns.get(CAMP_ID).topics
                     if t["path"] == "memory.keys")
        assert topic.get("sr"), "already-knows-it is evidence, lands on the topic"


class TestEncodingCap:
    def test_cap_two_per_packet_short_never_backfilled(self, api):
        for i in range(4):
            api.store.exercises.save(CAMP_ID, _present_ex(id=f"ex_p{i}"))
        pkt = build_packet(api.store, NOW, size=5)
        kinds = [api.store.exercises.get(c.campaign_id, c.exercise_id).kind
                 for c in pkt.items]
        assert kinds.count("present") == 2
        assert pkt.skipped.get("encoding_beyond_cap") == 2
        assert len(pkt.items) <= 3, "unused slots stay empty — short is correct"

    def test_reviews_never_displaced_by_encoding(self, api):
        for i in range(3):
            api.store.exercises.save(CAMP_ID, _present_ex(id=f"ex_p{i}"))
        due_sr = scheduling.record_outcome(
            scheduling.new_state(NOW - timedelta(days=6)), score=1.0, now=NOW - timedelta(days=5))
        api.store.exercises.save(CAMP_ID, Exercise(
            id="ex_r", topic_path="memory.keys", difficulty="beginner", kind="recall",
            answer="capture fast", prompt="first rule?", sr=due_sr,
        ))
        pkt = build_packet(api.store, NOW, size=5)
        served = {c.exercise_id for c in pkt.items}
        assert "ex_r" in served, "due review rides along regardless of the cap"


class TestHistoryWindow:
    def _rows(self, api: DojoAPI) -> str:
        return compiler.recent_rows(api.store, CAMP_ID, topic_path="memory.keys")

    def test_presentation_rides_near_verbatim_with_flag(self, api):
        api.store.exercises.save(CAMP_ID, _present_ex(quality="spent"))
        api.store.attempts.save(CAMP_ID, Attempt(
            id="att_p", session_id="s", exercise_id="ex_p", campaign_id=CAMP_ID,
            score=1.0, grader="exposure", reflected=True, latency_seconds=5.0,
            created_at=(NOW - timedelta(days=1)).isoformat(),
            prompt="Memorize the golden apple key.", user_answer="",
        ))
        rows = self._rows(api)
        assert 'presented: "the golden apple key: cat, tree, turmoil, hat"' in rows
        assert "awaiting first recall" in rows

    def test_flag_clears_after_graded_recall(self, api):
        self.test_presentation_rides_near_verbatim_with_flag(api)
        api.store.exercises.save(CAMP_ID, Exercise(
            id="ex_probe", topic_path="memory.keys", difficulty="intermediate",
            kind="skill", quality="spent", answer="turmoil", rubric="- exact",
            prompt="Third word of the golden apple key?",
        ))
        api.store.attempts.save(CAMP_ID, Attempt(
            id="att_probe", session_id="s", exercise_id="ex_probe", campaign_id=CAMP_ID,
            score=1.0, grader="ai", latency_seconds=8.0,
            created_at=NOW.isoformat(),
            prompt="Third word of the golden apple key?", user_answer="turmoil",
        ))
        rows = self._rows(api)
        assert "awaiting first recall" not in rows
        assert 'score 1.0 · "Third word of the golden apple key?"' in rows

    def test_cross_topic_calibration_line_and_empty_case(self, api):
        assert self._rows(api) == "(no practice on this topic yet)"
        api.store.exercises.save(CAMP_ID, Exercise(
            id="ex_other", topic_path="memory.rules", difficulty="beginner",
            kind="recall", answer="a", prompt="p",
        ))
        api.store.attempts.save(CAMP_ID, Attempt(
            id="att_o", session_id="s", exercise_id="ex_other", campaign_id=CAMP_ID,
            score=0.7, grader="ai", latency_seconds=9.0, created_at=NOW.isoformat(),
            prompt="p", user_answer="x",
        ))
        assert "other topics, last 1 graded: mean 0.70" in self._rows(api)
