"""dojo stats: the honesty surface — estimates tagged as estimates, records as
records, token spend visible per task kind (blueprint §11, I10)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from dojo import scheduling
from dojo.api import DojoAPI
from dojo.cli import main
from dojo.schemas import Attempt, Exercise

NOW = datetime(2026, 7, 8, 9, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_git():
    with patch("dojo.store.engine.init_git"), patch("dojo.store.engine.commit_git"):
        yield


@pytest.fixture
def api(tmp_path: Path) -> DojoAPI:
    api = DojoAPI(tmp_path)
    cid = api.create_campaign(name="French", topic_path="french", mission="NCLC 7.")["id"]
    fresh_sr = scheduling.record_outcome(
        scheduling.new_state(NOW - timedelta(days=2)), score=1.0,
        latency_seconds=5.0, now=NOW - timedelta(days=2),
    )
    api.store.exercises.save(cid, Exercise(
        id="ex_tracked", topic_path="french.vocab", difficulty="beginner",
        answer="x", prompt="?", sr=fresh_sr,
    ))
    api.store.exercises.save(cid, Exercise(
        id="ex_untracked", topic_path="french.vocab", difficulty="beginner",
        answer="y", prompt="??",
    ))
    api.store.attempts.save(cid, Attempt(
        id="att_1", session_id="s1", exercise_id="ex_tracked", campaign_id=cid,
        score=1.0, latency_seconds=5.0, grader="exact",
        created_at=(NOW - timedelta(days=2)).isoformat(), user_answer="x",
    ))
    api.store.attempts.save(cid, Attempt(
        id="att_2", session_id="s1", exercise_id="ex_untracked", campaign_id=cid,
        score=0.0, latency_seconds=20.0, skip_reason="forgot",
        created_at=(NOW - timedelta(days=1)).isoformat(), user_answer="",
    ))
    api._cid = cid
    return api


def test_stats_computes_honest_campaign_numbers(api: DojoAPI):
    res = api.stats(now=NOW)
    camp = res["campaigns"][0]
    assert camp["tracked_memories"] == 1
    assert 0.0 < camp["estimated_retention"] <= 1.0
    assert "estimate" in camp["retention_note"], "estimates must be tagged (I10)"
    assert camp["due_now"] == 1, "the never-practiced exercise is due; the fresh one is not"
    assert camp["recent_accuracy"] == 1.0, "skips are calibration signals, not graded answers"
    assert camp["days_since_practice"] == 1.0


def test_stats_reports_token_spend_per_kind(api: DojoAPI):
    from dojo.tasks import compiler, service

    compiled = compiler.compile_generate(
        api.store, api.store.campaigns.get(api._cid),
        topic_path="french.vocab", n_items=2, difficulty="beginner",
    )
    task = service.emit(api.store, compiled)
    service.submit(api.store, task.id, json.dumps({
        "items": [
            {"prompt": "Say dog in French.", "answer": "chien", "rubric": "- chien", "skill": "recall"},
            {"prompt": "Say cat in French.", "answer": "chat", "rubric": "- chat", "skill": "recall"},
        ],
        "note": None, "intervention": None,
    }))

    res = api.stats(now=NOW)
    spend = res["task_spend"]["exercise.generate"]
    assert spend["tasks"] == 1 and spend["fulfilled"] == 1
    assert spend["approx_prompt_tokens"] > 100, "real compiled payload, not zero"
    assert spend["approx_response_tokens"] > 10


def test_stats_cli_json_envelope(api: DojoAPI, capsys):
    rc = main(["--db", str(api.store.dojo_dir), "--json", "stats"])
    data = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0 and data["ok"]
    assert data["campaigns"][0]["name"] == "French"
    assert "estimates" in data["note"]
