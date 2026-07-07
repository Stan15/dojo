"""Task lifecycle tests — the I5 boundary (blueprint §6 correctness argument).

Pins: valid submissions apply exactly once (idempotent); every failure mode
(garbage, schema violations, mechanical cross-check failures) leaves domain
state byte-identical; bounded retries end in an honest `failed` status.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import pytest

from dojo.schemas import Attempt, Campaign, Exercise
from dojo.store import DojoStore
from dojo.tasks import compiler, service

CAMP_ID = "tef-french"


@pytest.fixture
def store(tmp_path: Path) -> DojoStore:
    s = DojoStore(tmp_path / "dojo")
    s.campaigns.save(Campaign(id=CAMP_ID, name="French TEF", mission="Reach NCLC 7."))
    return s


def domain_state_hash(store: DojoStore) -> str:
    """Hash of everything except task bookkeeping — the fuzz invariant is that
    failed submissions change nothing outside the task record itself."""
    h = hashlib.sha256()
    for path in sorted(store.dojo_dir.rglob("*")):
        rel = path.relative_to(store.dojo_dir)
        parts = rel.parts
        if not path.is_file() or parts[0] in {".git", "tasks"}:
            continue
        if rel.name in {".index.json", "dojo.log", "dojo.lock"}:
            continue
        h.update(str(rel).encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def emit_generate(store: DojoStore, n_items: int = 2) -> str:
    compiled = compiler.compile_generate(
        store, store.campaigns.get(CAMP_ID),
        topic_path="french.grammar", n_items=n_items, difficulty="intermediate",
    )
    return service.emit(store, compiled).id


def valid_generate_payload(n: int = 2) -> str:
    return json.dumps({
        "items": [
            {
                "prompt": f"Traduisez la phrase {i} : He would have gone.",
                "answer": "Il serait allé.",
                "rubric": "- être as auxiliary",
                "skill": "produce",
            }
            for i in range(n)
        ],
        "note": None,
    })


class TestGenerateHappyPath:
    def test_valid_submission_creates_candidates_and_fulfills(self, store: DojoStore):
        task_id = emit_generate(store, n_items=2)
        outcome = service.submit(store, task_id, valid_generate_payload(2))
        assert outcome.ok, outcome.errors
        assert outcome.status == "fulfilled"
        assert len(outcome.applied["candidates"]) == 2
        assert len(store.candidates.list(CAMP_ID)) == 2
        task = store.tasks.get(task_id)
        assert task.status == "fulfilled" and task.response_bytes > 0

    def test_resubmission_is_a_noop(self, store: DojoStore):
        task_id = emit_generate(store, n_items=2)
        service.submit(store, task_id, valid_generate_payload(2))
        again = service.submit(store, task_id, valid_generate_payload(2))
        assert again.ok and "already fulfilled" in again.applied["note"]
        assert len(store.candidates.list(CAMP_ID)) == 2, "idempotency: no duplicates"

    def test_fewer_items_with_note_accepted(self, store: DojoStore):
        task_id = emit_generate(store, n_items=3)
        payload = json.loads(valid_generate_payload(2))
        payload["note"] = "source too thin for a third distinct exercise"
        outcome = service.submit(store, task_id, json.dumps(payload))
        assert outcome.ok
        assert outcome.applied["note"].startswith("source too thin")

    def test_json_salvaged_from_fenced_prose(self, store: DojoStore):
        task_id = emit_generate(store, n_items=2)
        wrapped = f"Sure! Here you go:\n```json\n{valid_generate_payload(2)}\n```\nHope this helps!"
        assert service.submit(store, task_id, wrapped).ok

    def test_json_salvaged_from_harness_echo(self, store: DojoStore):
        """Harness CLIs echo the prompt (containing JSON skeletons) before the
        answer — the LAST top-level object must win."""
        task_id = emit_generate(store, n_items=2)
        task = store.tasks.get(task_id)
        harness_shaped = (
            "session id: 019f3ee0\n--------\nuser\n"
            f"{task.prompt}\n\n"          # echoed prompt, includes the OUTPUT skeleton
            "codex\n"
            f"{valid_generate_payload(2)}\n"
            "tokens used\n8 376\n"
            f"{valid_generate_payload(2)}\n"  # some harnesses repeat the final message
        )
        outcome = service.submit(store, task_id, harness_shaped)
        assert outcome.ok, outcome.errors
        assert len(store.candidates.list(CAMP_ID)) == 2


class TestGenerateRejections:
    def test_too_many_items_rejected(self, store: DojoStore):
        task_id = emit_generate(store, n_items=2)
        outcome = service.submit(store, task_id, valid_generate_payload(3))
        assert not outcome.ok and "exactly 2" in outcome.errors[0]
        assert store.candidates.list(CAMP_ID) == []

    def test_fewer_items_without_note_rejected(self, store: DojoStore):
        task_id = emit_generate(store, n_items=3)
        outcome = service.submit(store, task_id, valid_generate_payload(2))
        assert not outcome.ok and "note" in outcome.errors[0]

    def test_missing_rubric_rejected(self, store: DojoStore):
        task_id = emit_generate(store, n_items=1)
        payload = {"items": [{"prompt": "Traduisez.", "answer": "x", "rubric": None, "skill": "produce"}], "note": None}
        outcome = service.submit(store, task_id, json.dumps(payload))
        assert not outcome.ok and "answer and rubric" in outcome.errors[0]

    def test_bounded_retries_end_in_failed(self, store: DojoStore):
        task_id = emit_generate(store, n_items=2)
        for i in range(3):
            outcome = service.submit(store, task_id, "not json at all")
            assert not outcome.ok
        assert outcome.status == "failed"
        after = service.submit(store, task_id, valid_generate_payload(2))
        assert not after.ok and "re-emit" in after.errors[0]
        assert len(store.tasks.get(task_id).error_history) == 3


class TestFuzzInvariant:
    def test_garbage_never_touches_domain_state(self, store: DojoStore):
        """I5 fuzz pin: seeded garbage across the failure space leaves every
        non-task byte identical."""
        task_id = emit_generate(store, n_items=2)
        baseline = domain_state_hash(store)
        rng = random.Random(20260707)
        garbage = [
            "",
            "null",
            "[]",
            '{"items": []}',
            '{"items": "not-a-list"}',
            '{"wrong_key": 1}',
            '{"items": [{"prompt": "' + "w " * 500 + '", "skill": "produce"}]}',  # word-cap breach
            "".join(chr(rng.randint(33, 0x2FA0)) for _ in range(200)),
            '{"items": [{"prompt": "p", "answer": "a", "rubric": "r", "skill": "invented_skill"}]}',
        ]
        for i, payload in enumerate(garbage):
            # fresh task each time so max_submissions never gates the check
            tid = emit_generate(store, n_items=2) if i else task_id
            outcome = service.submit(store, tid, payload)
            assert not outcome.ok, f"garbage #{i} was accepted: {payload[:60]!r}"
            assert domain_state_hash(store) == baseline, (
                f"garbage #{i} mutated domain state: {payload[:60]!r}"
            )


class TestReflectApplier:
    def _seed_reflection(self, store: DojoStore) -> str:
        from dojo.schemas import Insight
        store.insights.save(CAMP_ID, Insight(
            id="ins_old", key="conditional.aux_choice",
            description="Picks avoir over être for motion verbs.",
        ))
        for i in range(3):
            store.attempts.save(CAMP_ID, Attempt(
                id=f"att_{i}", session_id="s1", exercise_id=f"ex_{i}", campaign_id=CAMP_ID,
                score=0.3, latency_seconds=10.0, user_answer="…",
            ))
        compiled = compiler.compile_reflect(store, store.campaigns.get(CAMP_ID), window_n=15)
        return service.emit(store, compiled).id

    def test_full_reflection_applies(self, store: DojoStore):
        task_id = self._seed_reflection(store)
        outcome = service.submit(store, task_id, json.dumps({
            "insight_updates": [
                {"op": "update", "id": "ins_old", "text": "Aux-choice errors persist under time pressure.",
                 "evidence": ["att_0", "att_2"], "reason": "same mistake twice more"},
                {"op": "create", "key": "listening.numbers", "text": "Mishears French decimal numbers in fast speech.",
                 "evidence": ["att_1"], "reason": "recurred across sessions"},
            ],
            "strategy": {"difficulty": None, "scaffolding": "high", "reason": "accuracy 0.3 over window"},
            "plan_revision": None,
            "journal": "Raised scaffolding; tracked new listening pattern.",
        }))
        assert outcome.ok, outcome.errors
        camp = store.campaigns.get(CAMP_ID)
        assert camp.strategy_profile["scaffolding"] == "high"
        assert camp.pedagogical_journal[-1]["action"] == "REFLECT"
        insights = {i.key: i for i in store.insights.list(CAMP_ID)}
        assert "listening.numbers" in insights
        assert "att_2" in insights["conditional.aux_choice"].sources
        assert all(store.attempts.get(CAMP_ID, f"att_{i}").reflected for i in range(3))

    def test_citing_unseen_attempt_rejected(self, store: DojoStore):
        task_id = self._seed_reflection(store)
        outcome = service.submit(store, task_id, json.dumps({
            "insight_updates": [
                {"op": "create", "key": "x.y", "text": "Invented pattern.",
                 "evidence": ["att_hallucinated"], "reason": "made up"},
            ],
            "strategy": None, "plan_revision": None, "journal": "no",
        }))
        assert not outcome.ok and "unknown attempt id" in outcome.errors[0]
        assert len(store.insights.list(CAMP_ID)) == 1, "state untouched"

    def test_touching_unknown_insight_rejected(self, store: DojoStore):
        task_id = self._seed_reflection(store)
        outcome = service.submit(store, task_id, json.dumps({
            "insight_updates": [
                {"op": "resolve", "id": "ins_ghost", "reason": "mastered"},
            ],
            "strategy": None, "plan_revision": None, "journal": "no",
        }))
        assert not outcome.ok and "unknown insight id" in outcome.errors[0]

    def test_three_creates_rejected_by_schema(self, store: DojoStore):
        task_id = self._seed_reflection(store)
        updates = [
            {"op": "create", "key": f"k.{i}", "text": "t", "evidence": ["att_0"], "reason": "r"}
            for i in range(3)
        ]
        outcome = service.submit(store, task_id, json.dumps({
            "insight_updates": updates, "strategy": None, "plan_revision": None, "journal": "j",
        }))
        assert not outcome.ok and any("new insights" in e for e in outcome.errors)


class TestPlanApplier:
    def test_plan_records_proposal_without_creating_state(self, store: DojoStore):
        compiled = compiler.compile_plan(store, goal="Learn Docker Compose in 3 weeks")
        task_id = service.emit(store, compiled).id
        before = len(store.campaigns.list())
        outcome = service.submit(store, task_id, json.dumps({
            "mission": "Debug and operate compose stacks during on-call.",
            "topics": [
                {"path": "docker.compose.services", "kind": "skill", "summary": "define and wire services"},
                {"path": "docker.compose.volumes", "kind": "recall", "summary": "volume syntax"},
            ],
            "phases": [
                {"phase": 1, "topics": ["docker.compose.services"],
                 "criteria": {"min_attempts": 5, "min_accuracy": 0.6}, "focus": "calibration"},
            ],
            "refinement_questions": ["Which compose version does your team run?"],
        }))
        assert outcome.ok, outcome.errors
        assert outcome.applied["refinement_questions"]
        assert len(store.campaigns.list()) == before, (
            "plan is a proposal (review-before-trust): no campaign until create"
        )


class TestGradeApplier:
    def _seed_attempt(self, store: DojoStore) -> tuple[str, Exercise]:
        ex = Exercise(
            id="ex_1", topic_path="french.grammar", difficulty="intermediate",
            answer="Il serait allé.", rubric="- être as auxiliary",
            prompt="Traduisez : He would have gone.",
        )
        store.exercises.save(CAMP_ID, ex)
        store.attempts.save(CAMP_ID, Attempt(
            id="att_1", session_id="s1", exercise_id="ex_1", campaign_id=CAMP_ID,
            score=0.0, latency_seconds=12.0, user_answer="Il aurait allé, je pense.",
        ))
        compiled = compiler.compile_grade(
            store, store.campaigns.get(CAMP_ID), ex,
            attempt_id="att_1", user_answer="Il aurait allé, je pense.",
        )
        return service.emit(store, compiled).id, ex

    def test_valid_grade_applies_with_provenance(self, store: DojoStore):
        task_id, _ = self._seed_attempt(store)
        outcome = service.submit(store, task_id, json.dumps({
            "score": 0.3,
            "evidence": "aurait allé",
            "feedback": "Right tense; aller takes être: il serait allé.",
            "error_tag": "aux choice",
        }))
        assert outcome.ok, outcome.errors
        att = store.attempts.get(CAMP_ID, "att_1")
        assert att.score == 0.3 and att.grader == "ai"
        assert att.error_tag == "aux choice"

    def test_hallucinated_evidence_rejected(self, store: DojoStore):
        task_id, _ = self._seed_attempt(store)
        outcome = service.submit(store, task_id, json.dumps({
            "score": 1.0,
            "evidence": "Il serait allé",  # from the answer KEY, not the learner
            "feedback": "Perfect.",
            "error_tag": None,
        }))
        assert not outcome.ok and "verbatim" in outcome.errors[0]
        assert store.attempts.get(CAMP_ID, "att_1").score == 0.0, "state untouched"

    def test_off_band_score_rejected_by_schema(self, store: DojoStore):
        task_id, _ = self._seed_attempt(store)
        outcome = service.submit(store, task_id, json.dumps({
            "score": 0.5, "evidence": "aurait", "feedback": "ok", "error_tag": None,
        }))
        assert not outcome.ok and any("score" in e for e in outcome.errors)
