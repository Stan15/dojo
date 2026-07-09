"""The ownership/visibility block (QUESTIONS.md 2026-07-09, STATE item 3).

(a) The learner model is inspectable (`dojo insights`), traceable to verbatim
answers (`insights show` — receipts + forward effect via generation
stamping), contestable in the learner's own words (`insights resolve
--because`, fed to the next reflection as its loudest feedback), and its
silent Tier-0 changes announce exactly once in daily.

(b) Campaign lifecycle: completion is deterministic and OBSERVED — all
phases passed flips the campaign to maintenance (ADR 005: reviews trickle,
no new material) and daily announces the three doors once; phase criteria
evaluate over a recent window so the end state is reachable; archive is a
human door; `dojo learn extend` reopens a maintained campaign.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dojo.api import DojoAPI
from dojo.schemas import Attempt, AttackPlanPhase, Campaign, Exercise, Insight
from dojo.tasks import compiler, service

CAMP_ID = "fr"


def iso(dt: datetime) -> str:
    return dt.isoformat()


@pytest.fixture
def api(tmp_path: Path) -> DojoAPI:
    a = DojoAPI(tmp_path / "dojo")
    a.store.campaigns.save(Campaign(
        id=CAMP_ID, name="French", mission="Speak French.", topic_path="fr",
        topics=[{"path": "fr.oral", "kind": "recall", "summary": ""}],
        attack_plan=[AttackPlanPhase(
            phase=1, topics=["fr.oral"],
            criteria={"min_attempts": 3, "min_accuracy": 0.8},
        )],
    ))
    return a


def add_attempt(api: DojoAPI, att_id: str, ex_id: str = "ex_1", *, score: float = 1.0,
                answer: str = "oui", when: datetime | None = None) -> None:
    api.store.attempts.save(CAMP_ID, Attempt(
        id=att_id, session_id="s1", exercise_id=ex_id, campaign_id=CAMP_ID,
        score=score, latency_seconds=5.0, grader="exact",
        prompt="dire oui?", user_answer=answer,
        created_at=iso(when or datetime.now(timezone.utc)),
    ))


def add_insight(api: DojoAPI, ins_id: str = "ins_1", *, key: str = "oral.hesitation",
                sources: list[str] | None = None, status: str = "active") -> None:
    api.store.insights.save(CAMP_ID, Insight(
        id=ins_id, key=key, status=status, sources=sources or [],
        description="Hesitates on spoken openers.",
    ))


class TestInsightVisibility:
    def test_list_shows_the_model_in_its_recorded_words(self, api):
        add_attempt(api, "att_1")
        add_insight(api, sources=["att_1"])
        res = api.insights_list()
        rows = res["campaigns"][0]["insights"]
        assert rows[0]["key"] == "oral.hesitation"
        assert rows[0]["description"] == "Hesitates on spoken openers."
        assert rows[0]["evidence_count"] == 1
        assert "markdown files" in res["note"], "direct edits are first-class"

    def test_resolved_only_under_all(self, api):
        add_insight(api, "ins_a", status="active")
        add_insight(api, "ins_r", key="oral.done", status="resolved")
        assert len(api.insights_list()["campaigns"][0]["insights"]) == 1
        assert len(api.insights_list(include_resolved=True)["campaigns"][0]["insights"]) == 2

    def test_show_renders_receipts_verbatim(self, api):
        add_attempt(api, "att_1", answer="euh... je pense que oui", score=0.3)
        add_insight(api, sources=["att_1", "att_gone"])
        res = api.insight_show("ins_1")
        assert res["receipts"][0]["your_answer"] == "euh... je pense que oui"
        assert res["receipts"][0]["grader"] == "exact", "I10: who scored it is part of the receipt"
        assert "no longer in the store" in res["receipts"][1]["note"], "missing evidence is honest"

    def test_generation_stamping_traces_forward_effect(self, api):
        add_insight(api)
        camp = api.store.campaigns.get(CAMP_ID)
        compiled = compiler.compile_generate(
            api.store, camp, topic_path="fr.oral", n_items=1, difficulty="beginner")
        assert compiled.context["targeted_insights"] == ["oral.hesitation"]
        task = service.emit(api.store, compiled)
        payload = json.dumps({"items": [{"prompt": "Ouvrez la conversation.",
                                         "answer": "bonjour", "rubric": "- greets",
                                         "skill": "recall"}], "note": None})
        assert service.submit(api.store, task.id, payload).ok
        api.promote_candidate(f"cand_{task.id[4:]}_0")
        res = api.insight_show("ins_1")
        assert res["effect"]["exercises_targeting"] == 1
        assert res["effect"]["last_7_days"] == 1

    def test_targeting_prefers_topic_affinity_then_freshness(self, api):
        for i, key in enumerate(["listening.speed", "oral.openers"]):
            api.store.insights.save(CAMP_ID, Insight(
                id=f"ins_{i}", key=key, description=f"about {key}",
                updated_at=iso(datetime.now(timezone.utc) - timedelta(days=i + 1)),
            ))
        picked = compiler.targeted_insights(api.store, CAMP_ID, k=1, topic_path="fr.oral")
        assert picked[0].key == "oral.openers", "topic match outranks recency"

    def test_resolve_stores_the_learner_verbatim_and_feeds_reflection(self, api):
        add_attempt(api, "att_1")
        add_insight(api)
        res = api.insight_resolve("ins_1", "I don't hesitate — I was cooking dinner.")
        assert res["status"] == "resolved"
        ins = api.store.insights.get(CAMP_ID, "ins_1")
        assert ins.resolution == "I don't hesitate — I was cooking dinner."
        compiled = compiler.compile_reflect(api.store, api.store.campaigns.get(CAMP_ID))
        assert "I was cooking dinner" in compiled.prompt, "learner voice reaches the next reflection"
        assert "[learner resolved insight oral.hesitation]" in compiled.prompt

    def test_resolve_requires_a_reason_and_rejects_double_resolve(self, api):
        add_insight(api)
        with pytest.raises(ValueError, match="own words"):
            api.insight_resolve("ins_1", "  ")
        api.insight_resolve("ins_1", "not true")
        with pytest.raises(ValueError, match="already resolved"):
            api.insight_resolve("ins_1", "again")

    def test_reflection_changes_announce_once_in_daily(self, api):
        add_attempt(api, "att_1")
        compiled = compiler.compile_reflect(api.store, api.store.campaigns.get(CAMP_ID))
        task = service.emit(api.store, compiled)
        payload = json.dumps({
            "insight_updates": [{"op": "create", "key": "oral.hesitation",
                                 "text": "Hesitates on openers.", "evidence": ["att_1"],
                                 "reason": "seen twice"}],
            "strategy": None, "plan_revision": None, "questions": [], "journal": "j",
        })
        assert service.submit(api.store, task.id, payload).ok
        first = api.daily()
        assert first["insight_notices"][0]["created"] == 1
        assert "dojo insights" in first["insight_notices"][0]["next"]
        second = api.daily(reset=True)
        assert "insight_notices" not in second, "announce exactly once"


class TestCampaignLifecycle:
    def pass_phase(self, api, *, scores: list[float]) -> None:
        api.store.exercises.save(CAMP_ID, Exercise(
            id="ex_1", topic_path="fr.oral", difficulty="beginner",
            answer="oui", prompt="dire oui?",
        ))
        for i, s in enumerate(scores):
            add_attempt(api, f"att_{i}", "ex_1", score=s)

    def test_windowed_criteria_let_a_bad_start_age_out(self, api):
        # Lifetime mean of 3×0.0 then 6×1.0 is 0.67 (< 0.8) — the old rule
        # stalls forever; the recent-window rule (last 2×min_attempts) passes.
        self.pass_phase(api, scores=[0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        camp = api.store.campaigns.get(CAMP_ID)
        api._evaluate_campaign_phase_advancement(camp)
        assert camp.active_phase_index == 1

    def test_completion_flips_to_maintenance_and_daily_announces_once(self, api):
        self.pass_phase(api, scores=[1.0, 1.0, 1.0])
        first = api.daily()
        camp = api.store.campaigns.get(CAMP_ID)
        assert camp.status == "maintenance"
        assert any(e["action"] == "CAMPAIGN_COMPLETE" for e in camp.pedagogical_journal)
        note = first["campaign_completions"][0]
        assert "archive" in note["next"] and "dojo learn" in note["next"], "three doors"
        assert "campaign_completions" not in api.daily(reset=True), "announced once"

    def test_maintenance_serves_reviews_but_never_new_material(self, api):
        self.pass_phase(api, scores=[1.0, 1.0, 1.0])
        api.daily()  # completes → maintenance
        now = datetime.now(timezone.utc)
        api.store.exercises.save(CAMP_ID, Exercise(  # a formed memory, due
            id="ex_rev", topic_path="fr.oral", difficulty="beginner",
            sr={"due": iso(now - timedelta(hours=1))}, answer="a", prompt="rev?",
        ))
        api.store.exercises.save(CAMP_ID, Exercise(  # never-practiced stock
            id="ex_fresh", topic_path="fr.oral", difficulty="beginner",
            answer="b", prompt="fresh?",
        ))
        from dojo import packet as packet_mod
        pkt = packet_mod.build_packet(api.store, now)
        ids = [i.exercise_id for i in pkt.items]
        assert "ex_rev" in ids, "retention trickle continues"
        assert "ex_fresh" not in ids, "no new material in maintenance"
        assert pkt.needs_generation == [], "maintenance requests nothing"

    def test_maintenance_reviews_count_as_review_debt(self, api):
        self.pass_phase(api, scores=[1.0, 1.0, 1.0])
        api.daily()
        now = datetime.now(timezone.utc)
        api.store.exercises.save(CAMP_ID, Exercise(
            id="ex_rev", topic_path="fr.oral", difficulty="beginner",
            sr={"due": iso(now + timedelta(days=2))}, answer="a", prompt="rev?",
        ))
        projected, _ = api._review_load_7d(now)
        assert projected == 1

    def test_learn_extend_reopens_a_maintained_campaign(self, api):
        self.pass_phase(api, scores=[1.0, 1.0, 1.0])
        api.daily()
        assert api.store.campaigns.get(CAMP_ID).status == "maintenance"
        res = api.learn("write French emails")
        task_id = res["tasks"][0]["id"]
        assert service.submit(api.store, task_id, json.dumps({
            "action": "new_topic", "campaign": CAMP_ID, "topic_path": "fr.writing",
            "new_name": None, "new_mission": None, "confidence": "high",
            "reason": "fits", "seed": False,
        })).ok
        api.learn_extend(task_id)
        camp = api.store.campaigns.get(CAMP_ID)
        assert camp.status == "active", "the extend door reopens execution"
        assert camp.active_phase_index == 1, "pointing at the appended phase"

    def test_campaign_list_shows_the_dashboard(self, api):
        self.pass_phase(api, scores=[1.0, 1.0, 1.0])
        api.daily()
        rows = api.campaign_list()["campaigns"]
        assert rows[0]["status"] == "maintenance" and rows[0]["complete"] is True
        assert rows[0]["phase"] == "1/1"

    def test_archive_leaves_rotation_and_daily(self, api):
        api.campaign_archive(CAMP_ID)
        assert api.store.campaigns.get(CAMP_ID) is None
        assert api.campaign_list()["campaigns"] == []
        with pytest.raises(ValueError, match="not found"):
            api.campaign_archive(CAMP_ID)

    def test_idle_campaign_gets_a_neutral_notice_with_doors(self, api):
        add_attempt(api, "att_old", when=datetime.now(timezone.utc) - timedelta(days=20))
        res = api.daily()
        idle = res["idle_campaigns"][0]
        assert idle["campaign_id"] == CAMP_ID and idle["days_idle"] >= 14
        assert "archive" in idle["next"] and "learn" in idle["next"]
        assert "streak" not in json.dumps(res).lower(), "no guilt vocabulary, ever"

    def test_never_practiced_campaign_is_new_not_idle(self, api):
        assert "idle_campaigns" not in api.daily()


class TestOwnershipCLI:
    def test_insights_json_envelope(self, api, capsys):
        from dojo.cli import main
        add_insight(api)
        rc = main(["--json", "--db", str(api.store.dojo_dir), "insights"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert out["ok"] and out["campaigns"][0]["insights"][0]["id"] == "ins_1"

    def test_campaign_list_and_archive_json(self, api, capsys):
        from dojo.cli import main
        assert main(["--json", "--db", str(api.store.dojo_dir), "campaign", "list"]) == 0
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert out["campaigns"][0]["campaign_id"] == CAMP_ID
        assert main(["--json", "--db", str(api.store.dojo_dir), "campaign", "archive", CAMP_ID]) == 0
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert out["status"] == "archived"
