"""Answer amendment (owner-approved 2026-07-13): /back for humans,
`dojo amend` for agents, one API underneath.

Pins: pending answers supersede (old answer kept verbatim in prior_answers,
stale grade task retired, fresh one emitted); repeated amendments
accumulate; N-step reach validates per target; landed grades refuse with
the dojo correct door (FSRS never double-fed); peek changes nothing.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from dojo.api import DojoAPI
from dojo.schemas import Exercise

CAMP = "fr"


@pytest.fixture(autouse=True)
def no_git():
    with patch("dojo.store.engine.init_git"), patch("dojo.store.engine.commit_git"):
        yield


@pytest.fixture
def api(tmp_path: Path) -> DojoAPI:
    a = DojoAPI(tmp_path)
    a.create_campaign(name="fr", topic_path="fr", mission="Speak.")
    # Two free-form exercises (rubric ⇒ pending AI grade) + one exact-match.
    for i in range(2):
        a.store.exercises.save(CAMP, Exercise(
            id=f"ex_free{i}", topic_path="fr.conv", difficulty="beginner",
            answer=f"réponse {i}", rubric="- correct", prompt=f"Q{i}?",
        ))
    a.store.exercises.save(CAMP, Exercise(
        id="ex_exact", topic_path="fr.vocab", difficulty="beginner",
        answer="chien", prompt="dog = ?",
    ))
    return a


def _run_session(api: DojoAPI, exercise_ids: list[str], answers: list[str]):
    from dojo.schemas import PracticeSession

    api.store.sessions.save_active(PracticeSession(id="sess_t", exercise_ids=exercise_ids))
    results = []
    for ans in answers:
        api.reveal_prompt()
        results.append(api.submit_answer(ans))
    return results


class TestAmendApi:
    def test_pending_answer_supersedes_and_reissues_grade_task(self, api):
        res = _run_session(api, ["ex_free0", "ex_free1"], ["first try", "second q answer"])
        old_task = res[0]["tasks"][0]["id"]

        out = api.amend_previous_answer("better answer", steps_back=2)
        assert out["ok"], out
        att = api.store.attempts.get(CAMP, res[0]["attempt_id"])
        assert att.user_answer == "better answer"
        assert att.prior_answers == ["first try"]
        assert api.store.tasks.get(old_task).status == "failed"
        assert api.store.tasks.get(out["tasks"][0]["id"]).status == "pending"

    def test_repeated_amendments_accumulate(self, api):
        res = _run_session(api, ["ex_free0"], ["v1"])
        api.amend_previous_answer("v2")
        api.amend_previous_answer("v3")
        att = api.store.attempts.get(CAMP, res[0]["attempt_id"])
        assert att.prior_answers == ["v1", "v2"] and att.user_answer == "v3"

    def test_landed_grade_refuses_with_correct_door(self, api):
        _run_session(api, ["ex_exact"], ["chien"])  # exact match → landed 1.0
        out = api.amend_previous_answer("chat")
        assert not out["ok"] and "already landed" in out["error"]
        assert "dojo correct" in out["next"]

    def test_beyond_session_start_refuses(self, api):
        _run_session(api, ["ex_free0"], ["a"])
        out = api.amend_previous_answer("b", steps_back=5)
        assert not out["ok"] and "before this session" in out["error"]

    def test_peek_changes_nothing(self, api):
        res = _run_session(api, ["ex_free0"], ["my answer"])
        peek = api.amend_previous_answer("", steps_back=1, peek=True)
        assert peek["ok"] and peek["current_answer"] == "my answer"
        att = api.store.attempts.get(CAMP, res[0]["attempt_id"])
        assert att.user_answer == "my answer" and att.prior_answers == []


class TestBackInSession:
    def test_slash_back_amends_mid_session(self, api, capsys):
        from dojo import interactive
        from dojo.schemas import PracticeSession

        api.store.sessions.save_active(PracticeSession(
            id="sess_h", exercise_ids=["ex_free0", "ex_free1"]))
        script = iter([
            "first stab",          # Q0
            "/back",               # from Q1: revisit Q0
            "much better answer",  # the replacement
            "/quit",               # leave before batch settle
        ])
        with patch.object(interactive, "_input", lambda prompt: next(script)):
            interactive.practice_loop(api, api.store.sessions.get_active().model_dump())
        out = capsys.readouterr().out
        assert "← back 1" in out and "first stab" in out
        assert "✓ amended" in out
        atts = api.store.attempts.list(CAMP)
        assert len(atts) == 1
        assert atts[0].user_answer == "much better answer"
        assert atts[0].prior_answers == ["first stab"]


class TestCampaignIdCollisions:
    """Owner 2026-07-15: archived ids count as taken (re-archiving a reused
    id would clobber the earlier archive); a suffixed id suffixes the
    display name too, so no two campaigns ever read identically."""

    def test_archived_id_is_taken_and_name_follows_suffix(self, tmp_path: Path):
        api = DojoAPI(tmp_path)
        api.create_campaign(name="French", topic_path="french", mission="Speak.")
        api.store.campaigns.archive("french")
        again = api.create_campaign(name="French", topic_path="french", mission="Again.")
        assert again["id"] == "french-2"
        assert again["name"] == "French (2)"
