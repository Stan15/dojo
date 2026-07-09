"""Change authority over AI plan revisions (QUESTIONS.md 2026-07-09).

The attack plan is a contract: minor/asked-for edits apply (journaled,
revertable, announced once); major inferred restructures become pending
proposals; questions become diagnostic exercises. Nothing restructures under
the learner's feet, and drip-edits are measured against the last plan the
learner explicitly confirmed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dojo.api import DojoAPI
from dojo.schemas import Attempt, AttackPlanPhase, Campaign
from dojo.store import DojoStore
from dojo.tasks import authority, compiler, service

CAMP_ID = "tef-french"


def phase(n: int, topics: list[str], attempts: int = 5, accuracy: float = 0.6,
          focus: str | None = None) -> dict:
    return {"phase": n, "topics": topics,
            "criteria": {"min_attempts": attempts, "min_accuracy": accuracy},
            "focus": focus}


BASE_PLAN = [phase(1, ["french.oral"]), phase(2, ["french.grammar"])]


@pytest.fixture
def store(tmp_path: Path) -> DojoStore:
    s = DojoStore(tmp_path / "dojo")
    camp = Campaign(
        id=CAMP_ID, name="French TEF", mission="Reach NCLC 7.",
        topic_path="french",
        attack_plan=[AttackPlanPhase.model_validate(p) for p in BASE_PLAN],
        pedagogical_journal=[{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "CREATE", "trigger": "test", "hypothesis": "seed",
            "status": "resolved", "plan_snapshot": BASE_PLAN,
        }],
    )
    s.campaigns.save(camp)
    return s


def seed_reflect_task(store: DojoStore, *, feedback: str | None = None) -> str:
    """Three graded attempts (att_2 optionally carrying learner feedback) and
    an emitted reflection task; returns the task id."""
    for i in range(3):
        store.attempts.save(CAMP_ID, Attempt(
            id=f"att_{i}", session_id="s1", exercise_id=f"ex_{i}", campaign_id=CAMP_ID,
            score=0.3, latency_seconds=10.0, user_answer="…", grader="exact",
            feedback=feedback if i == 2 else None,
        ))
    compiled = compiler.compile_reflect(store, store.campaigns.get(CAMP_ID), window_n=15)
    return service.emit(store, compiled).id


def reflect_payload(*, plan=None, evidence=(), questions=(), journal="j") -> str:
    body: dict = {"insight_updates": [], "strategy": None, "plan_revision": None,
                  "questions": list(questions), "journal": journal}
    if plan is not None:
        body["plan_revision"] = {"phases": plan, "evidence": list(evidence),
                                 "reason": "test revision"}
    return json.dumps(body)


class TestDeltaClassifier:
    def test_append_phase_is_minor(self):
        assert authority.classify_plan_delta(
            BASE_PLAN, BASE_PLAN + [phase(3, ["french.writing"])]) == "minor"

    def test_adding_a_topic_is_minor(self):
        prop = [phase(1, ["french.oral", "french.listening"]), BASE_PLAN[1]]
        assert authority.classify_plan_delta(BASE_PLAN, prop) == "minor"

    def test_relaxing_criteria_and_focus_text_are_minor(self):
        prop = [phase(1, ["french.oral"], attempts=3, accuracy=0.5, focus="new focus"),
                BASE_PLAN[1]]
        assert authority.classify_plan_delta(BASE_PLAN, prop) == "minor"

    def test_removing_a_topic_is_major(self):
        assert authority.classify_plan_delta(
            BASE_PLAN, [phase(1, ["french.oral"])] ) == "major"

    def test_moving_a_topic_between_phases_is_major(self):
        prop = [phase(1, ["french.grammar"]), phase(2, ["french.oral"])]
        assert authority.classify_plan_delta(BASE_PLAN, prop) == "major"

    def test_tightening_criteria_is_major(self):
        prop = [phase(1, ["french.oral"], attempts=8), BASE_PLAN[1]]
        assert authority.classify_plan_delta(BASE_PLAN, prop) == "major"

    def test_inserting_a_phase_before_existing_ones_is_major(self):
        prop = [phase(1, ["french.phonetics"]), *BASE_PLAN]
        assert authority.classify_plan_delta(BASE_PLAN, prop) == "major"


class TestReflectGating:
    def test_minor_revision_applies_with_snapshot_and_announcement(self, store):
        task_id = seed_reflect_task(store)
        prop = BASE_PLAN + [phase(3, ["french.writing"])]
        outcome = service.submit(store, task_id, reflect_payload(plan=prop))
        assert outcome.ok and outcome.applied["plan_revised"]
        camp = store.campaigns.get(CAMP_ID)
        assert len(camp.attack_plan) == 3
        entry = next(e for e in camp.pedagogical_journal
                     if e["action"] == authority.PLAN_APPLIED)
        assert entry["plan_snapshot"] == BASE_PLAN, "snapshot is the PRE-change plan"
        assert entry["announced"] is False

    def test_major_inferred_revision_is_proposed_not_applied(self, store):
        task_id = seed_reflect_task(store)
        prop = [phase(1, ["french.grammar"]), phase(2, ["french.oral"])]
        outcome = service.submit(store, task_id, reflect_payload(plan=prop))
        assert outcome.ok and outcome.applied["plan_proposed"]
        assert "dojo plan confirm" in outcome.applied["next"]
        camp = store.campaigns.get(CAMP_ID)
        assert [p.model_dump() for p in camp.attack_plan] == BASE_PLAN, "plan untouched"
        assert authority.pending_proposal(camp) is not None

    def test_major_revision_citing_learner_feedback_applies(self, store):
        task_id = seed_reflect_task(store, feedback="please drop grammar, exam is oral only")
        prop = [phase(1, ["french.oral"])]
        outcome = service.submit(store, task_id,
                                 reflect_payload(plan=prop, evidence=["att_2"]))
        assert outcome.ok and outcome.applied["plan_revised"], outcome.errors
        assert len(store.campaigns.get(CAMP_ID).attack_plan) == 1

    def test_evidence_without_learner_words_does_not_fast_path(self, store):
        task_id = seed_reflect_task(store)  # att_2 has NO feedback
        prop = [phase(1, ["french.oral"])]
        outcome = service.submit(store, task_id,
                                 reflect_payload(plan=prop, evidence=["att_2"]))
        assert outcome.ok and outcome.applied["plan_proposed"]

    def test_revision_citing_unknown_attempt_rejected(self, store):
        task_id = seed_reflect_task(store)
        outcome = service.submit(store, task_id, reflect_payload(
            plan=[phase(1, ["french.oral"])], evidence=["att_invented"]))
        assert not outcome.ok
        assert any("unknown attempt id" in e for e in outcome.errors)

    def test_anti_drip_measures_against_confirmed_baseline(self, store):
        # Tier-1 apply: relax phase-1 criteria 5 → 3 (minor vs baseline).
        t1 = seed_reflect_task(store)
        relaxed = [phase(1, ["french.oral"], attempts=3), BASE_PLAN[1]]
        assert service.submit(store, t1, reflect_payload(plan=relaxed)).ok
        # Re-tightening to 4 is major vs the CURRENT plan (3) but minor vs the
        # learner-confirmed baseline (5) — consent anchors at the baseline.
        t2 = seed_reflect_task(store)
        retightened = [phase(1, ["french.oral"], attempts=4), BASE_PLAN[1]]
        outcome = service.submit(store, t2, reflect_payload(plan=retightened))
        assert outcome.ok and outcome.applied["plan_revised"], outcome.errors
        # …but exceeding the baseline (6 > 5) is major: proposed, not applied.
        t3 = seed_reflect_task(store)
        beyond = [phase(1, ["french.oral"], attempts=6), BASE_PLAN[1]]
        outcome = service.submit(store, t3, reflect_payload(plan=beyond))
        assert outcome.ok and outcome.applied["plan_proposed"]

    def test_new_proposal_supersedes_pending_one(self, store):
        major = [phase(1, ["french.grammar"]), phase(2, ["french.oral"])]
        for _ in range(2):
            tid = seed_reflect_task(store)
            assert service.submit(store, tid, reflect_payload(plan=major)).ok
        camp = store.campaigns.get(CAMP_ID)
        proposals = [e for e in camp.pedagogical_journal
                     if e["action"] == authority.PLAN_PROPOSED]
        assert [p["status"] for p in proposals] == ["superseded", "pending"]

    def test_questions_become_diagnostic_exercises(self, store):
        task_id = seed_reflect_task(store)
        outcome = service.submit(store, task_id, reflect_payload(
            questions=["Is calculus prerequisite knowledge you once had, or new to you?"]))
        assert outcome.ok
        ids = outcome.applied["questions_as_diagnostics"]
        assert len(ids) == 1
        ex = store.exercises.get(CAMP_ID, ids[0])
        assert ex.quality == "diagnostic" and ex.topic_path == "french"


class TestLifecycle:
    def _propose(self, store) -> None:
        tid = seed_reflect_task(store)
        major = [phase(1, ["french.grammar"]), phase(2, ["french.oral"])]
        assert service.submit(store, tid, reflect_payload(plan=major)).ok

    def test_confirm_applies_and_moves_baseline(self, store, tmp_path):
        self._propose(store)
        api = DojoAPI(store.dojo_dir)
        res = api.plan_confirm()  # unambiguous: one campaign has a pending proposal
        assert res["status"] == "confirmed"
        camp = store.campaigns.get(CAMP_ID)
        assert camp.attack_plan[0].topics == ["french.grammar"]
        assert authority.pending_proposal(camp) is None
        assert authority.confirmed_plan_baseline(camp)[0]["topics"] == ["french.grammar"]

    def test_reject_leaves_plan_and_baseline_untouched(self, store):
        self._propose(store)
        api = DojoAPI(store.dojo_dir)
        assert api.plan_reject()["status"] == "rejected"
        camp = store.campaigns.get(CAMP_ID)
        assert [p.model_dump() for p in camp.attack_plan] == BASE_PLAN
        assert authority.pending_proposal(camp) is None
        assert authority.confirmed_plan_baseline(camp) == BASE_PLAN

    def test_revert_restores_pre_change_plan(self, store):
        tid = seed_reflect_task(store)
        minor = BASE_PLAN + [phase(3, ["french.writing"])]
        assert service.submit(store, tid, reflect_payload(plan=minor)).ok
        api = DojoAPI(store.dojo_dir)
        res = api.plan_revert()
        assert res["status"] == "reverted"
        camp = store.campaigns.get(CAMP_ID)
        assert [p.model_dump() for p in camp.attack_plan] == BASE_PLAN
        assert authority.last_revertable(camp) is None, "undo window closed"

    def test_confirm_without_pending_is_an_error(self, store):
        api = DojoAPI(store.dojo_dir)
        with pytest.raises(ValueError):
            api.plan_confirm(CAMP_ID)


class TestDailySurfacing:
    def test_proposal_repeats_and_applied_change_announces_once(self, store):
        # one applied (minor) change + one pending proposal
        t1 = seed_reflect_task(store)
        assert service.submit(store, t1, reflect_payload(
            plan=BASE_PLAN + [phase(3, ["french.writing"])])).ok
        t2 = seed_reflect_task(store)
        assert service.submit(store, t2, reflect_payload(
            plan=[phase(1, ["french.grammar"]), phase(2, ["french.oral"]),
                  phase(3, ["french.writing"])])).ok

        api = DojoAPI(store.dojo_dir)
        first = api.daily()
        assert first["plan_proposals"][0]["campaign_id"] == CAMP_ID
        assert "dojo plan show" in first["next"]
        assert first["plan_changes"][0]["campaign_id"] == CAMP_ID

        second = api.daily()
        assert "plan_changes" not in second, "applied changes announce exactly once"
        assert second["plan_proposals"], "proposals repeat until resolved"


class TestRevisionTopicHygiene:
    """A plan revision's topics (owner audit 2026-07-09): the model sees the
    unscheduled registry, new paths must be clean and shallow, and whatever
    an APPLIED revision schedules gets REGISTERED — no ghost topics that
    generation never stocks."""

    def test_reflect_payload_shows_unscheduled_registered_topics(self, store):
        camp = store.campaigns.get(CAMP_ID)
        camp.topics = [{"path": "french.listening", "kind": "skill", "summary": ""}]
        store.campaigns.save(camp)
        compiled = compiler.compile_reflect(store, camp)
        assert "registered topics not yet in any phase: french.listening" in compiled.prompt

    def test_new_phase_topic_shape_and_depth_rejected(self, store):
        for bad, msg in [("french.Formal Letters", "lowercase"),
                         ("french.a.b.c.d", "deeper than")]:
            task_id = seed_reflect_task(store)
            outcome = service.submit(store, task_id, reflect_payload(
                plan=BASE_PLAN + [phase(3, [bad])]))
            assert not outcome.ok and msg in "; ".join(outcome.errors), bad

    def test_applied_revision_registers_its_new_topics(self, store):
        task_id = seed_reflect_task(store)
        outcome = service.submit(store, task_id, reflect_payload(
            plan=BASE_PLAN + [phase(3, ["french.writing"])]))
        assert outcome.ok and outcome.applied["plan_revised"]
        camp = store.campaigns.get(CAMP_ID)
        assert any(t["path"] == "french.writing" and t["kind"] == "skill"
                   for t in camp.topics), "no ghost topics: scheduled ⇒ registered"

    def test_confirmed_proposal_registers_its_new_topics(self, store):
        task_id = seed_reflect_task(store)
        prop = [phase(1, ["french.grammar"]), phase(2, ["french.oral"]),
                phase(3, ["french.pronunciation"])]
        outcome = service.submit(store, task_id, reflect_payload(plan=prop))
        assert outcome.ok and outcome.applied["plan_proposed"]
        api = DojoAPI(store.dojo_dir)
        api.plan_confirm(CAMP_ID)
        camp = store.campaigns.get(CAMP_ID)
        assert any(t["path"] == "french.pronunciation" for t in camp.topics)
