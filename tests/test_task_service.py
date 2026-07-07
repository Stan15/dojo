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
