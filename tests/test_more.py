"""The capacity channel — `dojo more` + the daily-completion message
(QUESTIONS.md 2026-07-09, STATE item 2).

The learner's daily energy varies; `dojo more` is the INPUT for it — answered
at request only, never offered. Retention stays fixed (no re-drilling, no
pull-forward); acquisition is the dial, and every grant is checked against the
projected 7-day review debt. The completion message is the one discovery
surface, its copy is spec'd verbatim, and extension evidence is origin-marked
so reflection can discount appetite mode.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dojo.api import DojoAPI
from dojo.schemas import Attempt, Campaign, Candidate, Exercise
from dojo.tasks import compiler, service

CAMP_ID = "fr"

# The exact agent copy (owner-ruled): binds the harness to no-solicitation.
COMPLETE_NEXT = (
    "today's practice is complete — tell the learner it's done, playfully "
    "(go touch grass); tomorrow's session is what makes it stick (consistency "
    "beats volume); do not offer more practice unprompted; if the learner "
    "explicitly asks for more, run: dojo more --json"
)


def iso(dt: datetime) -> str:
    return dt.isoformat()


@pytest.fixture
def api(tmp_path: Path) -> DojoAPI:
    a = DojoAPI(tmp_path / "dojo")
    a.store.campaigns.save(Campaign(
        id=CAMP_ID, name="French", mission="Speak French.", topic_path="fr",
        topics=[{"path": "fr.oral", "kind": "recall", "summary": ""}],
    ))
    return a


def add_exercise(api: DojoAPI, ex_id: str, *, due: datetime | None = None,
                 topic: str = "fr.oral") -> None:
    """An active exercise: `due=None` means unattempted stock (no sr);
    a datetime becomes FSRS due state."""
    api.store.exercises.save(CAMP_ID, Exercise(
        id=ex_id, topic_path=topic, difficulty="beginner",
        sr={"due": iso(due)} if due else None,
        answer="oui", prompt=f"{ex_id}?",
    ))


def add_attempt(api: DojoAPI, att_id: str, ex_id: str, *, score: float = 1.0,
                when: datetime | None = None) -> None:
    api.store.attempts.save(CAMP_ID, Attempt(
        id=att_id, session_id="s1", exercise_id=ex_id, campaign_id=CAMP_ID,
        score=score, latency_seconds=5.0, grader="exact", user_answer="oui",
        created_at=iso(when or datetime.now(timezone.utc)),
    ))


class TestDailyCompletionMessage:
    def test_practiced_today_and_drained_says_done_with_the_exact_copy(self, api):
        now = datetime.now(timezone.utc)
        add_exercise(api, "ex_done", due=now + timedelta(days=2))
        add_attempt(api, "att_today", "ex_done", when=now)
        res = api.daily()
        assert res["session"] is None
        assert res["status"] == "complete_for_today"
        assert res["next"] == COMPLETE_NEXT, "the copy is spec'd verbatim"

    def test_no_practice_today_stays_an_honest_day_off(self, api):
        now = datetime.now(timezone.utc)
        add_exercise(api, "ex_done", due=now + timedelta(days=2))
        add_attempt(api, "att_old", "ex_done", when=now - timedelta(days=3))
        res = api.daily()
        assert res.get("status") is None
        assert "day off" in res["next"]
        assert "dojo more" not in res["next"], "no solicitation, ever"

    def test_a_live_packet_never_mentions_more(self, api):
        add_exercise(api, "ex_due")  # unattempted = due now
        res = api.daily()
        assert res["session"] is not None
        assert "more" not in json.dumps(res.get("next")), "no solicitation, ever"


class TestDebtGuard:
    def test_projection_counts_week_dues_including_overdue_topics_too(self, api):
        now = datetime.now(timezone.utc)
        add_exercise(api, "ex_over", due=now - timedelta(days=2))   # overdue counts
        add_exercise(api, "ex_soon", due=now + timedelta(days=3))   # inside horizon
        add_exercise(api, "ex_far", due=now + timedelta(days=12))   # outside
        add_exercise(api, "ex_fresh")                               # stock, not debt
        camp = api.store.campaigns.get(CAMP_ID)
        camp.topics.append({"path": "fr.skill", "kind": "skill",
                            "sr": {"due": iso(now + timedelta(days=1))}})
        api.store.campaigns.save(camp)
        projected, capacity = api._review_load_7d(now)
        assert projected == 3
        assert capacity == int(5 * 7 * 0.8)

    def test_over_budget_refuses_with_projection_and_alternative(self, api):
        now = datetime.now(timezone.utc)
        api.store.configs.set_value("daily.packet_size", "1")  # capacity 5
        for i in range(6):
            add_exercise(api, f"ex_d{i}", due=now + timedelta(hours=i))
        add_exercise(api, "ex_stock")
        res = api.more()
        assert res["extension_available"] is False
        assert res["projected_due_7d"] == 6 and res["capacity_7d"] == 5
        assert "debt" in res["reason"]
        assert "dojo start --topic" in res["alternative"], "the debt-free alternative"

    def test_force_overrides_guard_but_reports_the_debt(self, api):
        now = datetime.now(timezone.utc)
        api.store.configs.set_value("daily.packet_size", "1")
        for i in range(6):
            add_exercise(api, f"ex_d{i}", due=now + timedelta(hours=i))
        add_exercise(api, "ex_stock")
        res = api.more(force=True)
        assert res["extension_available"] is True and res["granted"] == 1
        assert "overridden" in res["warning"]
        assert res["projected_due_7d"] == 6, "inform, don't infantilize"


class TestSourcingAndCaps:
    def test_sourcing_order_stock_then_candidates_never_reviews(self, api):
        now = datetime.now(timezone.utc)
        add_exercise(api, "ex_rev", due=now - timedelta(hours=1))  # a due REVIEW
        add_exercise(api, "ex_new1")
        add_exercise(api, "ex_new2")
        api.store.candidates.save(CAMP_ID, Candidate(
            id="cand_1", topic_path="fr.oral", difficulty="beginner",
            answer="oui", rubric="- oui", prompt="cand?",
        ))
        res = api.more()
        ids = [i["exercise_id"] for i in res["items"]]
        assert ids == ["ex_new1", "ex_new2", "cand_1"], "unattempted → candidates, id-ordered"
        assert "ex_rev" not in ids, "extension NEVER serves reviews"
        assert res["granted"] == 3, "daily.extension_cap default"
        assert api.store.candidates.get(CAMP_ID, "cand_1") is None, "candidate was promoted"
        assert res["session"]["origin"] == "extension"

    def test_extension_cap_bounds_the_grant(self, api):
        api.store.configs.set_value("daily.extension_cap", "2")
        for i in range(5):
            add_exercise(api, f"ex_new{i}")
        res = api.more()
        assert res["granted"] == 2

    def test_no_stock_emits_one_generation_on_the_weakest_topic(self, api):
        camp = api.store.campaigns.get(CAMP_ID)
        camp.topics = [{"path": "fr.strong", "kind": "recall", "summary": ""},
                       {"path": "fr.weak", "kind": "recall", "summary": ""}]
        api.store.campaigns.save(camp)
        add_exercise(api, "ex_s", due=datetime.now(timezone.utc) + timedelta(days=9), topic="fr.strong")
        add_exercise(api, "ex_w", due=datetime.now(timezone.utc) + timedelta(days=9), topic="fr.weak")
        add_attempt(api, "att_s", "ex_s", score=1.0)
        add_attempt(api, "att_w", "ex_w", score=0.3)
        res = api.more()
        assert res["extension_available"] is True and res["session"] is None
        assert len(res["tasks"]) == 1, "at most ONE generation task"
        task = api.store.tasks.get(res["tasks"][0]["id"])
        assert task.context["topic_path"] == "fr.weak"
        assert task.context["auto_promote"] is True
        assert "run dojo more again" in res["next"]

    def test_no_stock_and_no_evidence_refuses_honestly(self, api):
        res = api.more()
        assert res["extension_available"] is False
        assert "no new material" in res["reason"]


class TestOncePerDayAndOriginMarking:
    def complete_extension(self, api) -> dict:
        """Grants a 1-item extension and answers it (exact match → session
        archives itself)."""
        add_exercise(api, "ex_new1")
        granted = api.more()
        assert granted["granted"] == 1
        api.reveal_prompt(session_id=granted["session"]["id"])
        return api.submit_answer("oui")

    def test_extension_attempts_carry_the_origin_marker(self, api):
        out = self.complete_extension(api)
        attempt = api.store.attempts.get(CAMP_ID, out["attempt_id"])
        assert attempt.origin == "extension"
        assert attempt.score == 1.0

    def test_second_grant_same_day_is_refused(self, api):
        self.complete_extension(api)
        add_exercise(api, "ex_new2")
        res = api.more()
        assert res["extension_available"] is False
        assert "already used" in res["reason"]

    def test_force_does_not_override_the_daily_cap(self, api):
        self.complete_extension(api)
        add_exercise(api, "ex_new2")
        assert api.more(force=True)["extension_available"] is False

    def test_open_session_means_finish_first(self, api):
        add_exercise(api, "ex_due")
        assert api.daily()["session"] is not None
        res = api.more()
        assert res["extension_available"] is False
        assert "finish it first" in res["reason"]

    def test_reflection_rows_label_extension_evidence(self, api):
        self.complete_extension(api)
        compiled = compiler.compile_reflect(api.store, api.store.campaigns.get(CAMP_ID))
        assert "extension (extra practice, learner-requested)" in compiled.prompt
        assert "learner-requested" not in compiled.prompt.split("extension")[0], \
            "only the extension row carries the label"


class TestMoreCLI:
    def test_json_envelope_refusal_is_ok_true(self, api, capsys):
        from dojo.cli import main
        rc = main(["--json", "--db", str(api.store.dojo_dir), "more"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert out["ok"] is True, "no is an answer, not an error"
        assert out["extension_available"] is False
        assert {"projected_due_7d", "capacity_7d", "reason", "alternative"} <= out.keys()
