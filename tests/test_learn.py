"""Route-first learning entry — `dojo learn` (QUESTIONS.md 2026-07-09, STATE item 1).

A learning goal routes against the registry BEFORE any new campaign is
planned: a near fit becomes the learner's extend-or-start-fresh choice
(extend = minor additive plan change under change authority; fresh = the full
plan pipeline seeded with the declined fit), propose_campaign hands off by
chaining a plan task, and routing is skipped entirely with zero campaigns or
an explicit --new.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dojo.api import DojoAPI
from dojo.schemas import AttackPlanPhase, Campaign, Exercise
from dojo.store import DojoStore
from dojo.tasks import authority, service

CAMP_ID = "tef-french"


def route_payload(action: str, *, campaign: str | None = None, topic: str | None = None,
                  new_name: str | None = None, new_mission: str | None = None) -> str:
    return json.dumps({
        "action": action, "campaign": campaign, "topic_path": topic,
        "new_name": new_name, "new_mission": new_mission,
        "confidence": "high", "reason": "test route", "seed": False,
    })


@pytest.fixture
def api(tmp_path: Path) -> DojoAPI:
    api = DojoAPI(tmp_path / "dojo")
    camp = Campaign(
        id=CAMP_ID, name="French TEF", mission="Reach NCLC 7.",
        topic_path="french",
        topics=[{"path": "french.oral", "kind": "skill", "summary": ""}],
        attack_plan=[AttackPlanPhase(
            phase=1, topics=["french.oral"],
            criteria={"min_attempts": 3, "min_accuracy": 0.8},
        )],
        pedagogical_journal=[{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "CREATE", "trigger": "test", "hypothesis": "seed",
            "status": "resolved",
            "plan_snapshot": [{"phase": 1, "topics": ["french.oral"],
                               "criteria": {"min_attempts": 3, "min_accuracy": 0.8},
                               "focus": None}],
        }],
    )
    api.store.campaigns.save(camp)
    return api


def routed_task(api: DojoAPI, goal: str, payload: str) -> str:
    """Emits a goal route for `goal`, submits `payload`, returns the task id."""
    res = api.learn(goal)
    assert res["mode"] == "route"
    task_id = res["tasks"][0]["id"]
    outcome = service.submit(api.store, task_id, payload)
    assert outcome.ok, outcome.errors
    return task_id


# ------------------------------------------------------------------
# Entry: when to route, when to skip straight to planning
# ------------------------------------------------------------------

class TestLearnEntry:
    def test_goal_routes_against_registry_when_campaigns_exist(self, api):
        res = api.learn("hold a conversation in French")
        assert res["mode"] == "route"
        task = api.store.tasks.get(res["tasks"][0]["id"])
        assert task.kind == "goal.route"
        assert "french.oral" in task.prompt, "registry digest must ground the router"
        assert "hold a conversation in French" in task.prompt

    def test_zero_campaigns_skip_routing(self, tmp_path):
        empty = DojoAPI(tmp_path / "empty")
        res = empty.learn("learn rust")
        assert res["mode"] == "plan"
        assert empty.store.tasks.get(res["tasks"][0]["id"]).kind == "campaign.plan"

    def test_explicit_new_skips_routing(self, api):
        res = api.learn("learn rust", new=True)
        assert res["mode"] == "plan"

    def test_empty_goal_rejected(self, api):
        with pytest.raises(ValueError):
            api.learn("   ")

    def test_payload_respects_route_budget(self, api):
        from dojo.tasks import compiler
        compiled = compiler.compile_goal_route(api.store, goal="learn French cooking")
        assert compiled.payload_bytes <= compiler.TOTAL_BUDGETS["goal.route"]


# ------------------------------------------------------------------
# The applier: review-before-trust, registry validation, handoff chaining
# ------------------------------------------------------------------

class TestGoalRouteApplier:
    def test_near_fit_writes_no_state_and_asks_the_learner(self, api):
        before = api.store.campaigns.get(CAMP_ID).model_dump()
        task_id = routed_task(api, "improve my spoken French",
                              route_payload("attach", campaign=CAMP_ID, topic="french.oral"))
        assert api.store.campaigns.get(CAMP_ID).model_dump() == before, \
            "a near fit is a QUESTION, not a mutation"
        applied = api.store.tasks.get(task_id).context["_applied"]
        assert f"dojo learn extend {task_id}" in applied["next"]
        assert f"dojo learn new {task_id}" in applied["next"]

    def test_attach_to_unknown_topic_rejected(self, api):
        res = api.learn("improve my spoken French")
        outcome = service.submit(api.store, res["tasks"][0]["id"],
                                 route_payload("attach", campaign=CAMP_ID, topic="french.made_up"))
        assert not outcome.ok and "does not exist" in "; ".join(outcome.errors)

    def test_stay_inbox_rejected_for_goals(self, api):
        res = api.learn("something vague")
        outcome = service.submit(api.store, res["tasks"][0]["id"], route_payload("stay_inbox"))
        assert not outcome.ok
        assert "disposition" in "; ".join(outcome.errors)

    def test_propose_campaign_chains_a_seeded_plan_task(self, api):
        task_id = routed_task(api, "learn woodworking",
                              route_payload("propose_campaign", new_name="Woodworking",
                                            new_mission="Build real furniture by hand."))
        applied = api.store.tasks.get(task_id).context["_applied"]
        handoff = applied["handoff"]
        plan_task = api.store.tasks.get(handoff["id"])
        assert plan_task.kind == "campaign.plan"
        assert "learn woodworking" in plan_task.prompt, "seeded with the goal verbatim"
        assert "Woodworking" in plan_task.prompt, "router's name hint rides along"
        assert f"campaign create --from-task {plan_task.id}" in applied["next"]


# ------------------------------------------------------------------
# learn extend: deterministic minor additive plan change under authority
# ------------------------------------------------------------------

class TestLearnExtend:
    def test_new_topic_extends_plan_under_authority(self, api):
        task_id = routed_task(api, "write formal French emails",
                              route_payload("new_topic", campaign=CAMP_ID, topic="french.writing"))
        res = api.learn_extend(task_id)
        camp = api.store.campaigns.get(CAMP_ID)
        assert res["phase_appended"] == 2 and res["plan_change"] == "minor_additive"
        assert camp.attack_plan[-1].topics == ["french.writing"]
        assert "write formal French emails" in camp.attack_plan[-1].focus
        assert any(t["path"] == "french.writing" and t["kind"] == "skill"
                   for t in camp.topics)
        entry = next(e for e in camp.pedagogical_journal
                     if e["action"] == authority.PLAN_APPLIED)
        assert entry["announced"] is False, "next daily announces it once"
        assert entry["plan_snapshot"][-1]["phase"] == 1, "snapshot is the PRE-change plan"
        # The appended phase is additive against the confirmed baseline.
        assert authority.classify_plan_delta(
            entry["plan_snapshot"], [p.model_dump() for p in camp.attack_plan]) == "minor"

    def test_extension_is_announced_by_daily_and_revertable(self, api):
        task_id = routed_task(api, "write formal French emails",
                              route_payload("new_topic", campaign=CAMP_ID, topic="french.writing"))
        api.learn_extend(task_id)
        proposals, changes = api._plan_notices()
        assert not proposals and len(changes) == 1
        assert changes[0]["campaign_id"] == CAMP_ID
        reverted = api.plan_revert(CAMP_ID)
        assert [p["phase"] for p in reverted["plan"]] == [1]

    def test_extend_is_idempotent(self, api):
        task_id = routed_task(api, "write formal French emails",
                              route_payload("new_topic", campaign=CAMP_ID, topic="french.writing"))
        api.learn_extend(task_id)
        again = api.learn_extend(task_id)
        assert again["already_applied"] is True
        assert len(api.store.campaigns.get(CAMP_ID).attack_plan) == 2, "no duplicate phase"

    def test_attach_already_covered_by_pending_phase_changes_nothing(self, api):
        task_id = routed_task(api, "improve my spoken French",
                              route_payload("attach", campaign=CAMP_ID, topic="french.oral"))
        res = api.learn_extend(task_id)
        assert res["already_covered"] is True and res["phase"] == 1
        assert len(api.store.campaigns.get(CAMP_ID).attack_plan) == 1
        assert "topic-boost" in res["next"], "boosting, not restructuring"

    def test_attach_to_completed_topic_appends_a_refocus_phase(self, api):
        camp = api.store.campaigns.get(CAMP_ID)
        camp.active_phase_index = 1  # phase 1 done; french.oral is behind the learner
        api.store.campaigns.save(camp)
        task_id = routed_task(api, "get my spoken French back",
                              route_payload("attach", campaign=CAMP_ID, topic="french.oral"))
        res = api.learn_extend(task_id)
        assert res["phase_appended"] == 2

    def test_extend_on_propose_campaign_route_refuses(self, api):
        task_id = routed_task(api, "learn woodworking",
                              route_payload("propose_campaign", new_name="Woodworking",
                                            new_mission="Build real furniture."))
        with pytest.raises(ValueError, match="nothing to extend"):
            api.learn_extend(task_id)

    def test_extend_on_unfulfilled_task_refuses(self, api):
        res = api.learn("improve my spoken French")
        with pytest.raises(ValueError, match="fulfill it first"):
            api.learn_extend(res["tasks"][0]["id"])


# ------------------------------------------------------------------
# learn new: declined fit hands off to the full plan pipeline
# ------------------------------------------------------------------

class TestLearnNew:
    def test_declined_fit_seeds_plan_with_the_refusal(self, api):
        task_id = routed_task(api, "French for business meetings",
                              route_payload("new_topic", campaign=CAMP_ID, topic="french.business"))
        res = api.learn_new(task_id)
        assert res["mode"] == "plan"
        plan_task = api.store.tasks.get(res["tasks"][0]["id"])
        assert plan_task.kind == "campaign.plan"
        assert "French for business meetings" in plan_task.prompt
        assert "declined extending" in plan_task.prompt, \
            "planner must know a near fit was refused, to scope a SEPARATE campaign"
        assert CAMP_ID in plan_task.prompt

    def test_registry_topics_ride_along(self, api):
        task_id = routed_task(api, "French for business meetings",
                              route_payload("new_topic", campaign=CAMP_ID, topic="french.business"))
        res = api.learn_new(task_id)
        assert "french.oral" in api.store.tasks.get(res["tasks"][0]["id"]).prompt


# ------------------------------------------------------------------
# CLI grammar: goal vs verbs, agent envelope, no interactive leaks
# ------------------------------------------------------------------

class TestLearnCLI:
    def run(self, api: DojoAPI, argv: list[str], capsys) -> dict:
        from dojo.cli import main
        rc = main(["--json", "--db", str(api.store.dojo_dir), "learn", *argv])
        assert rc == 0
        return json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    def test_goal_envelope(self, api, capsys):
        out = self.run(api, ["hold", "a", "French", "conversation"], capsys)
        assert out["ok"] and out["mode"] == "route"
        assert out["tasks"][0]["id"].startswith("tsk_")
        assert "next" in out

    def test_verb_extend_parses_and_resolves(self, api, capsys):
        task_id = routed_task(api, "write formal French emails",
                              route_payload("new_topic", campaign=CAMP_ID, topic="french.writing"))
        out = self.run(api, ["extend", task_id], capsys)
        assert out["phase_appended"] == 2

    def test_verb_new_parses_and_resolves(self, api, capsys):
        task_id = routed_task(api, "French for business meetings",
                              route_payload("new_topic", campaign=CAMP_ID, topic="french.business"))
        out = self.run(api, ["new", task_id], capsys)
        assert out["mode"] == "plan"

    def test_json_bad_verb_target_fails_honestly(self, api):
        from dojo.cli import main
        with pytest.raises(SystemExit, match="not found"):
            main(["--json", "--db", str(api.store.dojo_dir), "learn", "extend", "tsk_missing"])
