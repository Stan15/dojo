"""End-to-end loops through the task architecture (ADR 010).

These are the product's two core journeys, driven the way a harness drives
them — commands emit tasks, "the model" (this test) fulfills them via the same
submit path, and the deterministic core carries all state in between:

  1. onboarding: campaign → diagnostic task → calibration session → reflection
     task → insights/strategy applied
  2. content: source → generation task → candidates → review gate → practice
     session → deterministic + AI-graded answers
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dojo.api import DojoAPI
from dojo.schemas import AttackPlanPhase, CriteriaEntry
from dojo.tasks import service


@pytest.fixture(autouse=True)
def no_git(tmp_path):
    with patch("dojo.store.engine.init_git"), patch("dojo.store.engine.commit_git"):
        yield


def fulfill(api: DojoAPI, task_ref: dict, payload: dict) -> None:
    outcome = service.submit(api.store, task_ref["id"], json.dumps(payload))
    assert outcome.ok, f"fulfillment rejected: {outcome.errors}"


def test_onboarding_diagnostic_and_reflection_loop(tmp_path: Path):
    api = DojoAPI(tmp_path)

    # 1. Create the campaign in diagnostic mode (what `dojo campaign create` does)
    res = api.create_campaign(
        name="French TEF", topic_path="language.french.tef",
        mission="Reach NCLC 7 oral French by October",
    )
    campaign_id = res["id"]
    camp = api.store.campaigns.get(campaign_id)
    camp.strategy_profile = {"mode": "diagnostic", "difficulty": "intermediate", "scaffolding": "high"}
    camp.attack_plan = [AttackPlanPhase(
        phase=0, topics=["language.french.tef.diagnostic"],
        criteria=CriteriaEntry(min_attempts=2, min_accuracy=0.0),
    )]
    camp.active_phase_index = 0
    api.store.campaigns.save(camp)

    # 2. Starting a session with nothing due emits a diagnostic task, no session (I4)
    sess_res = api.start_practice_session(campaign_id=campaign_id)
    assert sess_res["session"] is None
    assert sess_res["tasks"], "a diagnostic generation task must be emitted"
    task_ref = sess_res["tasks"][0]

    # 3. "The model" fulfills the diagnostic task → exercises appear directly
    fulfill(api, task_ref, {
        "items": [
            {"prompt": "How comfortable are you holding a 2-minute conversation in French?",
             "answer": None, "rubric": None, "skill": "diagnostic"},
            {"prompt": "What deadline are you working toward, if any?",
             "answer": None, "rubric": None, "skill": "diagnostic"},
        ],
        "note": None,
    })
    diagnostics = api.store.exercises.list(campaign_id, filters={"quality": "diagnostic"})
    assert len(diagnostics) == 2, "diagnostics bypass the candidate gate"

    # 4. Now the session starts; answers auto-score with provenance
    sess_res = api.start_practice_session(campaign_id=campaign_id)
    session_id = sess_res["session"]["id"]
    for answer in ("I freeze after simple phrases.", "TEF exam on October 12."):
        api.reveal_prompt(session_id=session_id)
        ans = api.submit_answer(user_answer=answer, session_id=session_id)
        assert ans["score"] == 1.0 and ans["grader"] == "auto"

    # 5. Consolidation emits a reflection task over the unreflected evidence
    cons = api.consolidate_learner_profile(campaign_id=campaign_id)
    assert cons["status"] == "tasks_emitted"
    reflect_ref = cons["tasks"][0]
    attempt_ids = [a.id for a in api.store.attempts.list(campaign_id)]

    fulfill(api, reflect_ref, {
        "insight_updates": [{
            "op": "create", "key": "oral.freeze_after_openers",
            "text": "Freezes after opening phrases in conversation.",
            "evidence": [attempt_ids[0]], "reason": "self-reported at onboarding",
        }],
        "strategy": {"difficulty": "beginner", "scaffolding": "high",
                     "reason": "self-assessed early-stage oral ability"},
        "plan_revision": {
            "phases": [
                {"phase": 1, "topics": ["language.french.tef.diagnostic"],
                 "criteria": {"min_attempts": 5, "min_accuracy": 0.6},
                 "focus": "guided conversation openers"},
            ],
            "reason": "deadline Oct 12: start guided oral drills now",
        },
        "journal": "Calibrated to beginner with high scaffolding; oral drills first.",
    })

    # 6. The learning loop closed: insights, strategy, plan, journal, evidence marks
    camp = api.store.campaigns.get(campaign_id)
    assert camp.strategy_profile["difficulty"] == "beginner"
    assert camp.attack_plan[0].focus == "guided conversation openers"
    assert camp.pedagogical_journal[-1]["action"] == "REFLECT"
    insights = api.store.insights.list(campaign_id)
    assert [i.key for i in insights] == ["oral.freeze_after_openers"]
    assert all(a.reflected for a in api.store.attempts.list(campaign_id))

    # 7. Reflection with no new evidence refuses to churn
    again = api.consolidate_learner_profile(campaign_id=campaign_id)
    assert again["status"] == "nothing_to_reflect"


def test_source_to_graded_practice_loop(tmp_path: Path):
    api = DojoAPI(tmp_path)
    res = api.create_campaign(
        name="French TEF", topic_path="french",
        mission="Reach NCLC 7 oral French",
    )
    campaign_id = res["id"]

    # 1. Ingesting with --generate emits a grounded generation task
    src_res = api.add_source(
        title="Conditionnel passé notes",
        content=("# Le conditionnel passé\n\nSe forme avec l'auxiliaire au conditionnel "
                 "présent suivi du participe passé. Les verbes de mouvement utilisent être."),
        kind="text", generate_candidates=True, topic="french.grammar.conditional",
    )
    assert src_res["tasks"], "generation task expected"

    fulfill(api, src_res["tasks"][0], {
        "items": [
            # one recall-lane item (verbatim fact, FSRS on the item itself) and
            # two skill-lane items (disposable; memory lives on the topic)
            {"prompt": "Quel auxiliaire pour les verbes de mouvement au conditionnel passé ?",
             "answer": "être", "rubric": "- says être", "skill": "recall"},
            {"prompt": "Traduisez : He would have gone.",
             "answer": "Il serait allé.", "rubric": "- être as auxiliary",
             "skill": "produce"},
            {"prompt": "Traduisez : She would have come.",
             "answer": "Elle serait venue.", "rubric": "- être as auxiliary",
             "skill": "produce"},
        ],
        "note": None,
    })
    candidates = api.store.candidates.list(campaign_id)
    assert len(candidates) == 3, "practice items land as candidates (review gate, I2)"
    assert api.store.exercises.list(campaign_id) == [], "nothing active before review"

    # 2. Review gate: promote two of three
    for cand in candidates[:2]:
        api.promote_candidate(cand.id)
    assert len(api.store.exercises.list(campaign_id)) == 2

    # 3. Practice: one exact-match recall answer, one free-form skill → grade task
    sess = api.start_practice_session(campaign_id=campaign_id)
    session_id = sess["session"]["id"]

    answers = {}
    for _ in range(2):
        prompt_info = api.reveal_prompt(session_id=session_id)
        ex = api.store.exercises.get(campaign_id, prompt_info["exercise_id"])
        if ex.kind == "recall":
            answers["recall"] = api.submit_answer(user_answer="être", session_id=session_id)
        else:
            answers["skill"] = api.submit_answer(
                user_answer="Il aurait allé, je crois.", session_id=session_id
            )

    exact = answers["recall"]
    assert exact["score"] == 1.0 and exact["grader"] == "exact" and not exact["pending_grade"]
    freeform = answers["skill"]
    assert freeform["pending_grade"] and freeform["grader"] is None

    fulfill(api, freeform["tasks"][0], {
        "score": 0.3,
        "evidence": "aurait allé",
        "feedback": "Right tense; aller takes être: il serait allé.",
        "error_tag": "aux choice",
    })
    attempt = api.store.attempts.get(campaign_id, freeform["attempt_id"])
    assert attempt.score == 0.3 and attempt.grader == "ai" and attempt.error_tag == "aux choice"

    # 4. Both memory lanes advanced at FINAL scores only (ADR 012/014):
    #    recall → FSRS on the item; skill → FSRS on the topic + item retires.
    from datetime import datetime, timezone
    from dojo import scheduling
    now = datetime.now(timezone.utc)

    recall_ex = api.store.exercises.get(campaign_id, exact["exercise_id"])
    assert recall_ex.sr is not None and not scheduling.is_due(recall_ex.sr, now), (
        "a perfect recall answer schedules the item away"
    )

    skill_ex = api.store.exercises.get(campaign_id, freeform["exercise_id"])
    assert skill_ex.sr is None and skill_ex.quality == "spent", (
        "skill items are disposable: no per-item memory, retired after use"
    )
    campaign = api.store.campaigns.get(campaign_id)
    topic = next(t for t in campaign.topics if t["path"] == "french.grammar.conditional")
    assert topic["sr"]["last_review"] is not None, "skill memory lives on the topic node"
    assert scheduling.due_at(topic["sr"]) - now < __import__("datetime").timedelta(days=1), (
        "a 0.3 lapse on the topic comes back fast"
    )


def test_skip_signals_advance_the_memory_model(tmp_path: Path):
    from dojo.schemas import Exercise

    api = DojoAPI(tmp_path)
    campaign_id = api.create_campaign(
        name="Vocab", topic_path="vocab", mission="Retain core vocabulary.",
    )["id"]
    for i, prompt in enumerate(["mot un", "mot deux"]):
        api.store.exercises.save(campaign_id, Exercise(
            id=f"ex_{i}", topic_path="vocab.core", difficulty="beginner",
            answer="x", prompt=prompt,
        ))
    session_id = api.start_practice_session(campaign_id=campaign_id)["session"]["id"]

    api.reveal_prompt(session_id=session_id)
    api.skip_active_exercise("too_easy", session_id=session_id)
    ex0 = api.store.exercises.get(campaign_id, "ex_0")
    assert ex0.quality == "too_easy", "archived out of rotation"
    assert ex0.sr is not None, "an Easy review still feeds the memory model"

    api.reveal_prompt(session_id=session_id)
    api.skip_active_exercise("forgot", session_id=session_id)
    ex1 = api.store.exercises.get(campaign_id, "ex_1")
    from dojo import scheduling
    from datetime import datetime, timedelta, timezone
    assert ex1.quality not in ("archived", "too_easy"), "forgot keeps the item in rotation"
    assert scheduling.due_at(ex1.sr) - datetime.now(timezone.utc) < timedelta(days=1), (
        "a retrieval failure comes back fast"
    )
