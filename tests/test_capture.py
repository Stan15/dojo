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
