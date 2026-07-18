"""Capture → route → confirm → file tests (ADR 013, Q6).

Pins: capture is durable before any AI runs; routes to nonexistent targets are
structurally impossible; the validated route is a PROPOSAL awaiting the
learner by default; confirmation makes the capture an ordinary Source wired
into its campaign; autofile is opt-in; the daily envelope nags about waiting
captures so the inbox cannot silently rot.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dojo.api import DojoAPI
from dojo.schemas import Exercise
from dojo.tasks import service


@pytest.fixture(autouse=True)
def no_git():
    with patch("dojo.store.engine.init_git"), patch("dojo.store.engine.commit_git"):
        yield


@pytest.fixture
def api(tmp_path: Path) -> DojoAPI:
    api = DojoAPI(tmp_path)
    cid = api.create_campaign(name="French TEF", topic_path="french",
                              mission="Reach NCLC 7.")["id"]
    camp = api.store.campaigns.get(cid)
    camp.topics = [{"path": "french.grammar.conditional", "kind": "recall", "summary": ""}]
    api.store.campaigns.save(camp)
    api._test_campaign_id = cid
    return api


def route_payload(**overrides) -> str:
    base = {
        "action": "attach",
        "campaign": None, "topic_path": None,
        "new_name": None, "new_mission": None,
        "confidence": "high", "reason": "grammar fact fits conditional topic",
        "seed": False,
    }
    base.update(overrides)
    return json.dumps(base)


class TestCaptureDurability:
    def test_capture_is_saved_before_any_ai_runs(self, api: DojoAPI):
        res = api.capture("Motion verbs take être in past conditional", why="TEF prep")
        cap = api.store.captures.get(res["capture_id"])
        assert cap is not None and cap.status == "unrouted"
        assert cap.text.startswith("Motion verbs")
        assert res["tasks"][0]["kind"] == "capture.route"


class TestRouteValidation:
    def test_nonexistent_campaign_rejected(self, api: DojoAPI):
        res = api.capture("some fact")
        outcome = service.submit(api.store, res["tasks"][0]["id"], route_payload(
            campaign="invented-campaign", topic_path="french.grammar.conditional",
        ))
        assert not outcome.ok and "not in the registry" in outcome.errors[0]
        assert api.store.captures.get(res["capture_id"]).status == "unrouted"

    def test_nonexistent_topic_rejected_for_attach(self, api: DojoAPI):
        cid = api._test_campaign_id
        res = api.capture("some fact")
        outcome = service.submit(api.store, res["tasks"][0]["id"], route_payload(
            campaign=cid, topic_path="french.invented.topic",
        ))
        assert not outcome.ok and "does not exist" in outcome.errors[0]

    def test_new_topic_hangs_off_existing_parent(self, api: DojoAPI):
        cid = api._test_campaign_id
        res = api.capture("Subjunctive triggers after il faut que")
        outcome = service.submit(api.store, res["tasks"][0]["id"], route_payload(
            action="new_topic", campaign=cid, topic_path="french.grammar.subjunctive",
        ))
        assert outcome.ok, outcome.errors
        assert api.store.captures.get(res["capture_id"]).status == "proposed"


class TestConfirmByDefault:
    def test_high_confidence_route_still_waits_for_confirmation(self, api: DojoAPI):
        """Q6: the owner chose confirm-by-default over autofile."""
        cid = api._test_campaign_id
        res = api.capture("Motion verbs take être in past conditional")
        outcome = service.submit(api.store, res["tasks"][0]["id"], route_payload(
            campaign=cid, topic_path="french.grammar.conditional",
        ))
        assert outcome.ok and outcome.applied["filed"] is None
        cap = api.store.captures.get(res["capture_id"])
        assert cap.status == "proposed" and cap.source_id is None

        filed = api.inbox_confirm(res["capture_id"])
        cap = api.store.captures.get(res["capture_id"])
        assert cap.status == "filed" and cap.source_id == filed["source_id"]
        source = api.store.sources.get(filed["source_id"])
        assert source.kind == "capture" and "être" in source.content
        camp = api.store.campaigns.get(cid)
        assert any(link["source_id"] == source.id for link in camp.sources_config)

    def test_autofile_optin_files_high_confidence_immediately(self, api: DojoAPI):
        api.store.configs.set_value("capture.autofile", "true")
        cid = api._test_campaign_id
        res = api.capture("Motion verbs take être in past conditional")
        outcome = service.submit(api.store, res["tasks"][0]["id"], route_payload(
            campaign=cid, topic_path="french.grammar.conditional", seed=True,
        ))
        assert outcome.ok and outcome.applied["filed"] is not None
        cap = api.store.captures.get(res["capture_id"])
        assert cap.status == "filed"
        assert outcome.applied["filed"]["tasks"], "seed=true emits a generation task"

    def test_route_next_binds_the_agent_to_ask_the_learner(self, api: DojoAPI):
        """Owner ruling 2026-07-18: the envelope's next must direct the agent
        to ASK the learner before confirming — a new campaign especially is
        never auto-confirmed. Belt to SKILL.md's suspenders."""
        cid = api._test_campaign_id
        res = api.capture("Motion verbs take être in past conditional")
        outcome = service.submit(api.store, res["tasks"][0]["id"], route_payload(
            campaign=cid, topic_path="french.grammar.conditional",
        ))
        nxt = outcome.applied["next"]
        assert "ask" in nxt and "french.grammar.conditional" in nxt
        assert "on their yes" in nxt

        res2 = api.capture("Beeswax melts at 62-64C")
        outcome2 = service.submit(api.store, res2["tasks"][0]["id"], route_payload(
            action="propose_campaign", campaign=None, topic_path=None,
            new_name="Candle Making", new_mission="Pour clean-burning candles at home.",
        ))
        nxt2 = outcome2.applied["next"]
        assert "ASK the learner" in nxt2 and "Candle Making" in nxt2
        assert "Only on their yes" in nxt2

    def test_seeded_generation_carries_the_learners_why(self, api: DojoAPI):
        """Owner core-need audit 2026-07-18 (QUESTIONS 6g): the capture's WHY
        must reach the seeded generation payload, so practice aims at what
        the learner cares about in the material — not the material generally."""
        cid = api._test_campaign_id
        res = api.capture(
            "Motion verbs take être in past conditional",
            why="I keep saying 'aurait venu' to my tutor",
        )
        outcome = service.submit(api.store, res["tasks"][0]["id"], route_payload(
            campaign=cid, topic_path="french.grammar.conditional", seed=True,
        ))
        filed = api.inbox_confirm(res["capture_id"])
        task = api.store.tasks.get(filed["tasks"][0]["id"])
        assert "aurait venu" in task.prompt, "the learner's why is in the payload"
        assert "aim the practice at that" in task.prompt

    def test_seeded_generation_without_why_is_unchanged(self, api: DojoAPI):
        """No why → the SOURCE section renders exactly as before (golden
        safety: the why line appears only when a why exists)."""
        cid = api._test_campaign_id
        res = api.capture("Motion verbs take être in past conditional")
        service.submit(api.store, res["tasks"][0]["id"], route_payload(
            campaign=cid, topic_path="french.grammar.conditional", seed=True,
        ))
        filed = api.inbox_confirm(res["capture_id"])
        task = api.store.tasks.get(filed["tasks"][0]["id"])
        assert "## SOURCE\n" in task.prompt
        assert "saved this because" not in task.prompt

    def test_propose_campaign_chains_a_plan_task_and_stamps_diagnostic(self, api: DojoAPI):
        """Q 6g item 3: a capture-born campaign no longer dead-ends bare —
        filing emits a campaign.plan task seeded with the router's mission +
        the learner's why, and the campaign starts in calibration like every
        other creation door."""
        res = api.capture("Bees fan their wings to cool the hive below 36C",
                          why="starting two hives next spring")
        outcome = service.submit(api.store, res["tasks"][0]["id"], route_payload(
            action="propose_campaign", campaign=None, topic_path=None,
            new_name="Backyard Beekeeping", new_mission="Keep two hives alive through the seasons.",
        ))
        assert outcome.ok
        filed = api.inbox_confirm(res["capture_id"])
        camp = api.store.campaigns.get(filed["campaign_id"])
        assert camp.strategy_profile.get("mode") == "diagnostic", "same stamp as other doors"
        plan_refs = [t for t in filed["tasks"]]
        plan_task = api.store.tasks.get(plan_refs[0]["id"])
        assert plan_task.kind == "campaign.plan"
        assert "starting two hives next spring" in plan_task.prompt, "the why seeds the plan"
        assert f"--into {camp.id}" in filed["next"], "the consent step is named"

    def test_materialize_into_initializes_a_bare_campaign_and_refuses_established(self, api: DojoAPI, tmp_path):
        """--into applies a reviewed proposal onto the bare capture-born
        campaign (topics, phases, mission, PLAN_CONFIRMED journal); a campaign
        that already has a plan refuses — those change through authority."""
        import json as _json
        from dojo.cli import _materialize_core
        from dojo.tasks import flows as _flows
        from dojo.tasks import authority

        res = api.capture("Bees fan their wings to cool the hive below 36C",
                          why="starting two hives next spring")
        service.submit(api.store, res["tasks"][0]["id"], route_payload(
            action="propose_campaign", campaign=None, topic_path=None,
            new_name="Backyard Beekeeping", new_mission="Keep two hives alive through the seasons.",
        ))
        filed = api.inbox_confirm(res["capture_id"])
        plan_task_id = filed["tasks"][0]["id"]
        proposal = {
            "mission": "Keep two hives healthy from install to spring.",
            "name": "Backyard Beekeeping",
            "topics": [
                {"path": "beekeeping.inspection.brood", "kind": "skill", "summary": "reading brood frames"},
                {"path": "beekeeping.winter.prep", "kind": "recall", "summary": "winterization checklist"},
            ],
            "phases": [
                {"topics": ["beekeeping.inspection.brood"],
                 "criteria": {"min_attempts": 5, "min_accuracy": 0.0}, "focus": "calibration"},
                {"topics": ["beekeeping.inspection.brood", "beekeeping.winter.prep"],
                 "criteria": {"min_attempts": 10, "min_accuracy": 0.7}, "focus": "core husbandry"},
            ],
            "refinement_questions": [],
        }
        outcome = service.submit(api.store, plan_task_id, _json.dumps(proposal))
        assert outcome.ok, outcome.errors
        result = _materialize_core(api, plan_task_id, None, into=filed["campaign_id"])
        camp = api.store.campaigns.get(filed["campaign_id"])
        assert camp.mission == "Keep two hives healthy from install to spring."
        assert len(camp.attack_plan) == 2 and camp.attack_plan[0].criteria.min_accuracy == 0.0
        assert any(t["path"] == "beekeeping.winter.prep" for t in camp.topics)
        assert camp.pedagogical_journal[-1]["action"] == authority.PLAN_CONFIRMED
        assert result["id"] == filed["campaign_id"]

        # Established campaigns refuse --into.
        second = _flows.request_plan(api.store, goal="more bees",
                                     context_notes="", existing_topics="")
        outcome2 = service.submit(api.store, second.id, _json.dumps(proposal))
        assert outcome2.ok
        import pytest as _pytest
        with _pytest.raises(SystemExit, match="already has a plan"):
            _materialize_core(api, second.id, None, into=filed["campaign_id"])

    def test_low_confidence_never_autofiles(self, api: DojoAPI):
        api.store.configs.set_value("capture.autofile", "true")
        cid = api._test_campaign_id
        res = api.capture("might be grammar, might be vocab")
        outcome = service.submit(api.store, res["tasks"][0]["id"], route_payload(
            campaign=cid, topic_path="french.grammar.conditional", confidence="low",
        ))
        assert outcome.ok and outcome.applied["filed"] is None
        assert api.store.captures.get(res["capture_id"]).status == "proposed"


class TestInboxLifecycle:
    def test_propose_campaign_confirm_creates_campaign(self, api: DojoAPI):
        res = api.capture("The Wilhelm scream appears in over 400 films")
        outcome = service.submit(api.store, res["tasks"][0]["id"], route_payload(
            action="propose_campaign", new_name="Film Trivia",
            new_mission="Retain great film trivia for conversations.",
        ))
        assert outcome.ok
        api.inbox_confirm(res["capture_id"])
        camp = api.store.campaigns.get("film-trivia")
        assert camp is not None and "trivia" in camp.mission.lower()

    def test_dismiss_and_daily_nag(self, api: DojoAPI):
        cid = api._test_campaign_id
        api.store.exercises.save(cid, Exercise(
            id="ex_due", topic_path="french.grammar.conditional",
            difficulty="beginner", answer="x", prompt="?",
        ))
        res = api.capture("something to think about")
        daily = api.daily()
        assert daily["inbox_waiting"] == 1
        assert "awaiting a home" in daily["next"]

        api.inbox_dismiss(res["capture_id"])
        assert api.store.captures.get(res["capture_id"]).status == "dismissed"
        daily = api.daily(reset=True)
        assert daily["inbox_waiting"] == 0
