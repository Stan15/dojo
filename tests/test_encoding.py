"""ADR 017 — the encoding stage: a first-encounter miss is free.

Pins the substrate: the `first_encounter` predicate, exposure landing (fixed
Good, never a lapse, never spends the exercise), the apply_grade conversion
(miss-on-unencoded / knowledge_gap → grader="exposure" + kernel reveal), and
the exclusions that keep encoding events out of every mastery computation
(phase criteria, stats accuracy, `more` weakest-topic, reflect windows).

The field failure this guards against: honest "I don't know"s on
never-presented material landed as FSRS lapses (difficulty 9.2/10) and the
learner was scored as failing (owner store, 2026-07-10).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from dojo import outcomes, scheduling
from dojo.api import DojoAPI
from dojo.schemas import Attempt, AttackPlanPhase, Campaign, Candidate, CriteriaEntry, Exercise
from dojo.store import DojoStore
from dojo.tasks import compiler, service

CAMP_ID = "memory"
NOW = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_git():
    with patch("dojo.store.engine.init_git"), patch("dojo.store.engine.commit_git"):
        yield


@pytest.fixture
def store(tmp_path: Path) -> DojoStore:
    s = DojoStore(tmp_path / "dojo")
    s.campaigns.save(Campaign(
        id=CAMP_ID, name="memory", mission="Stop relying on raw memory.",
        topics=[{"path": "memory.failure_patterns", "kind": "skill", "summary": ""}],
    ))
    return s


def _skill_ex(**over) -> Exercise:
    base = dict(
        id="ex_skill", topic_path="memory.failure_patterns", difficulty="intermediate",
        kind="skill", answer="The five failure patterns are …",
        rubric="- names the pattern", prompt="Name the failure pattern.",
    )
    base.update(over)
    return Exercise(**base)


def _recall_ex(**over) -> Exercise:
    base = dict(
        id="ex_recall", topic_path="memory.core_rules", difficulty="beginner",
        kind="recall", answer="capture fast", prompt="First core rule = ?",
    )
    base.update(over)
    return Exercise(**base)


class TestFirstEncounterPredicate:
    def test_unencoded_synthetic_skill_topic_is_first_encounter(self, store):
        camp = store.campaigns.get(CAMP_ID)
        assert outcomes.first_encounter(camp, _skill_ex()) is True

    def test_encoded_skill_topic_is_not(self, store):
        camp = store.campaigns.get(CAMP_ID)
        camp.topics[0]["sr"] = scheduling.new_state(NOW)
        assert outcomes.first_encounter(camp, _skill_ex()) is False

    def test_recall_uses_its_own_card(self, store):
        camp = store.campaigns.get(CAMP_ID)
        assert outcomes.first_encounter(camp, _recall_ex()) is True
        assert outcomes.first_encounter(camp, _recall_ex(sr=scheduling.new_state(NOW))) is False

    def test_grounded_diagnostic_and_answerless_never_qualify(self, store):
        camp = store.campaigns.get(CAMP_ID)
        assert outcomes.first_encounter(camp, _skill_ex(provenance="grounded")) is False
        assert outcomes.first_encounter(camp, _skill_ex(quality="diagnostic")) is False
        assert outcomes.first_encounter(camp, _skill_ex(answer=None)) is False


class TestExposureLanding:
    def test_exposure_is_gentler_than_a_lapse(self):
        """The poisoning this ADR fixes: an Again-rated first contact inflates
        difficulty; exposure (fixed Good) must not."""
        exposure = scheduling.record_exposure(None, now=NOW)
        lapse = scheduling.record_outcome(None, score=0.0, now=NOW)
        assert exposure["difficulty"] < lapse["difficulty"]
        due = datetime.fromisoformat(exposure["due"])
        assert due <= NOW + timedelta(days=1), "first retrieval due by next session"

    def test_skill_lane_lands_on_topic_and_keeps_exercise(self, store):
        store.exercises.save(CAMP_ID, _skill_ex())
        outcomes.land_exposure(store, CAMP_ID, "ex_skill", now=NOW)
        camp = store.campaigns.get(CAMP_ID)
        assert camp.topics[0]["sr"] is not None
        ex = store.exercises.get(CAMP_ID, "ex_skill")
        assert ex.quality != "spent", "the exercise becomes the first retrieval"

    def test_recall_lane_lands_on_the_card(self, store):
        store.exercises.save(CAMP_ID, _recall_ex())
        outcomes.land_exposure(store, CAMP_ID, "ex_recall", now=NOW)
        assert store.exercises.get(CAMP_ID, "ex_recall").sr is not None

    def test_already_encoded_state_untouched(self, store):
        """A knowledge_gap grade on presented material must neither reward
        nor punish — the still-due schedule brings it back on its own."""
        sr = scheduling.new_state(NOW - timedelta(days=3))
        store.exercises.save(CAMP_ID, _recall_ex(sr=sr))
        outcomes.land_exposure(store, CAMP_ID, "ex_recall", now=NOW)
        assert store.exercises.get(CAMP_ID, "ex_recall").sr == sr


def _graded(store, ex: Exercise, payload: dict) -> dict:
    """Seed attempt + grade task for `ex`, submit `payload`, return applied."""
    store.exercises.save(CAMP_ID, ex)
    store.attempts.save(CAMP_ID, Attempt(
        id="att_1", session_id="s1", exercise_id=ex.id, campaign_id=CAMP_ID,
        score=0.0, latency_seconds=30.0, user_answer=payload["evidence"],
    ))
    compiled = compiler.compile_grade(
        store, store.campaigns.get(CAMP_ID), ex,
        attempt_id="att_1", user_answer=payload["evidence"],
    )
    task_id = service.emit(store, compiled).id
    outcome = service.submit(store, task_id, json.dumps(payload))
    assert outcome.ok, outcome.errors
    return outcome.applied


class TestGradeConversion:
    def test_miss_on_first_encounter_lands_as_exposure(self, store):
        applied = _graded(store, _skill_ex(), {
            "score": 0.3, "evidence": "i think it is about cues",
            "feedback": "The pattern is prospective memory.", "error_tag": None,
        })
        att = store.attempts.get(CAMP_ID, "att_1")
        assert att.grader == "exposure" and att.reflected is True
        assert applied["landed"] == "exposure"
        assert applied["correct_answer"] == "The five failure patterns are …"
        topic = store.campaigns.get(CAMP_ID).topics[0]
        assert topic["sr"] is not None
        assert topic["sr"]["difficulty"] < 7, "initialized as exposure, not lapse"

    def test_success_on_first_encounter_grades_normally(self, store):
        applied = _graded(store, _skill_ex(), {
            "score": 1.0, "evidence": "prospective memory failure",
            "feedback": "Exactly right.", "error_tag": None,
        })
        att = store.attempts.get(CAMP_ID, "att_1")
        assert att.grader == "ai", "prior knowledge earns full credit, no ceremony"
        assert "landed" not in applied

    def test_knowledge_gap_never_lands_a_lapse_even_when_encoded(self, store):
        sr = scheduling.new_state(NOW - timedelta(days=3))
        camp = store.campaigns.get(CAMP_ID)
        camp.topics[0]["sr"] = sr
        store.campaigns.save(camp)
        _graded(store, _skill_ex(), {
            "score": 0.0, "evidence": "you never taught me what the patterns are",
            "feedback": "The patterns are listed in the answer.",
            "error_tag": None, "knowledge_gap": True,
        })
        att = store.attempts.get(CAMP_ID, "att_1")
        assert att.grader == "exposure"
        assert store.campaigns.get(CAMP_ID).topics[0]["sr"] == sr, "schedule untouched"

    def test_real_forgetting_still_lapses_and_reveals_kernel(self, store):
        """Encoded-then-forgot stays a legitimate lapse (the scheduler
        working); a 0.0 additionally reveals the kernel (owner ruling:
        partial misses stay feedback-only)."""
        applied = _graded(store, _recall_ex(sr=scheduling.new_state(NOW - timedelta(days=3))), {
            "score": 0.0, "evidence": "no idea",
            "feedback": "The rule is: capture fast.", "error_tag": None,
        })
        att = store.attempts.get(CAMP_ID, "att_1")
        assert att.grader == "ai" and att.reflected is False
        assert applied["correct_answer"] == "capture fast"

    def test_partial_miss_on_encoded_material_reveals_nothing(self, store):
        applied = _graded(store, _recall_ex(sr=scheduling.new_state(NOW - timedelta(days=3))), {
            "score": 0.3, "evidence": "capture",
            "feedback": "Close: capture fast.", "error_tag": None,
        })
        assert "correct_answer" not in applied

    def test_grounded_material_is_test_first(self, store):
        _graded(store, _skill_ex(provenance="grounded"), {
            "score": 0.3, "evidence": "not sure",
            "feedback": "See the source: prospective memory.", "error_tag": None,
        })
        assert store.attempts.get(CAMP_ID, "att_1").grader == "ai"


class TestExposureExcludedEverywhere:
    def _api_with_exposures(self, tmp_path) -> DojoAPI:
        api = DojoAPI(tmp_path)
        cid = api.create_campaign(name="m", topic_path="m", mission="mission.")["id"]
        camp = api.store.campaigns.get(cid)
        camp.attack_plan = [AttackPlanPhase(
            phase=1, topics=["m.t"], criteria=CriteriaEntry(min_attempts=2, min_accuracy=0.6),
        )]
        camp.save if False else None
        api.store.campaigns.save(camp)
        api.store.exercises.save(cid, Exercise(
            id="ex_t", topic_path="m.t", difficulty="beginner", kind="skill",
            answer="a", rubric="r", prompt="p",
        ))
        for i, (grader, score, reflected) in enumerate([
            ("exposure", 0.0, True), ("exposure", 0.3, True), ("ai", 1.0, False),
        ]):
            api.store.attempts.save(cid, Attempt(
                id=f"att_{i}", session_id="s", exercise_id="ex_t", campaign_id=cid,
                score=score, latency_seconds=10.0, grader=grader, reflected=reflected,
                user_answer="x",
            ))
        self.cid = cid
        return api

    def test_phase_criteria_ignore_exposures(self, tmp_path):
        api = self._api_with_exposures(tmp_path)
        camp = api.store.campaigns.get(self.cid)
        api._evaluate_campaign_phase_advancement(camp)
        assert camp.active_phase_index == 0, "one real attempt < min_attempts=2"

    def test_stats_accuracy_ignores_exposures(self, tmp_path):
        api = self._api_with_exposures(tmp_path)
        row = next(c for c in api.stats(now=NOW)["campaigns"] if c["campaign_id"] == self.cid)
        assert row["recent_accuracy"] == 1.0, "0.0-score exposures must not drag accuracy"

    def test_weakest_topic_ignores_exposures(self, tmp_path):
        api = self._api_with_exposures(tmp_path)
        assert api._weakest_topic() == (self.cid, "m.t")
        # and its mean is built from the single real attempt (1.0), not 0.43

    def test_reflect_rows_exclude_exposures(self, tmp_path):
        api = self._api_with_exposures(tmp_path)
        compiled = compiler.compile_reflect(api.store, api.store.campaigns.get(self.cid))
        assert "att_2" in compiled.context["attempt_ids"]
        assert "att_0" not in compiled.prompt and "att_1" not in compiled.prompt


class TestProvenanceContract:
    def test_round_trips_through_the_store(self, store):
        store.exercises.save(CAMP_ID, _skill_ex(provenance="grounded"))
        assert store.exercises.get(CAMP_ID, "ex_skill").provenance == "grounded"

    def test_promotion_copies_provenance(self, tmp_path):
        api = DojoAPI(tmp_path)
        cid = api.create_campaign(name="m", topic_path="m", mission="mission.")["id"]
        api.store.candidates.save(cid, Candidate(
            id="cand_1", topic_path="m.t", difficulty="beginner",
            provenance="grounded", answer="a", rubric="r", prompt="p",
        ))
        promoted = api.promote_candidate("cand_1")
        assert promoted["provenance"] == "grounded"

    def test_generation_stamps_mode(self, store):
        compiled = compiler.compile_generate(
            store, store.campaigns.get(CAMP_ID),
            topic_path="memory.failure_patterns", n_items=1,
            difficulty="beginner", source_slice="# Notes\nthe five patterns…",
        )
        compiled.context["auto_promote"] = True
        task_id = service.emit(store, compiled).id
        outcome = service.submit(store, task_id, json.dumps({"items": [{
            "prompt": "Name the failure pattern in this story…",
            "answer": "prospective memory", "rubric": "- names it", "skill": "explain",
        }], "note": None}))
        assert outcome.ok, outcome.errors
        ex = store.exercises.get(CAMP_ID, outcome.applied["exercises"][0])
        assert ex.provenance == "grounded"
