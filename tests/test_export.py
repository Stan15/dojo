"""dojo export: the data-portability guarantee (ADR 011). Export reads every
entity through the Store protocol — blind to the backend — and writes a fresh,
self-contained markdown store. With today's markdown backend that's a clean
tree; when a database backend exists, the same command is the escape hatch."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dojo.api import DojoAPI
from dojo.cli import main
from dojo.export import export_store
from dojo.schemas import Attempt, Capture, Exercise, Insight, Source
from dojo.store import DojoStore


@pytest.fixture(autouse=True)
def no_git():
    with patch("dojo.store.engine.init_git"), patch("dojo.store.engine.commit_git"):
        yield


@pytest.fixture
def populated(tmp_path: Path) -> DojoAPI:
    api = DojoAPI(tmp_path / "src-store")
    cid = api.create_campaign(name="French", topic_path="french", mission="NCLC 7.")["id"]
    api.store.sources.save(Source(id="src_1", title="Notes — été", kind="text",
                                  content="Le conditionnel passé…"))
    api.store.exercises.save(cid, Exercise(
        id="ex_1", topic_path="french.grammar", difficulty="beginner",
        answer="être", prompt="Auxiliaire des verbes de mouvement ?",
        sr={"card_id": 1, "state": 2, "step": None, "stability": 2.3,
            "difficulty": 4.1, "due": "2026-07-09T00:00:00+00:00",
            "last_review": "2026-07-07T00:00:00+00:00"},
    ))
    api.store.attempts.save(cid, Attempt(
        id="att_1", session_id="s1", exercise_id="ex_1", campaign_id=cid,
        score=1.0, latency_seconds=9.0, grader="exact", user_answer="être",
    ))
    api.store.insights.save(cid, Insight(id="ins_1", key="a.b", description="Pattern."))
    api.store.captures.save(Capture(id="cap_1", text="TIL something", why="curiosity"))
    api.store.configs.set_value("daily.packet_size", 6)
    api._cid = cid
    return api


def test_export_round_trips_through_the_protocol(populated: DojoAPI, tmp_path: Path):
    dest = tmp_path / "exported"
    summary = export_store(populated.store, dest)
    assert summary["counts"] == {
        "sources": 1, "captures": 1, "campaigns": 1, "exercises": 1,
        "attempts": 1, "insights": 1, "config_values": 1,
    }

    out = DojoStore(dest)
    cid = populated._cid
    assert out.campaigns.get(cid).model_dump() == populated.store.campaigns.get(cid).model_dump()
    assert out.exercises.get(cid, "ex_1").model_dump() == \
        populated.store.exercises.get(cid, "ex_1").model_dump(), "sr state survives"
    assert out.attempts.get(cid, "att_1").grader == "exact"
    assert out.captures.get("cap_1").why == "curiosity"
    assert out.configs.get_value("daily.packet_size") == 6
    assert out.doctor.run()["Root directory layout"] == [], "export is a valid store"


def test_export_refuses_nonempty_destination(populated: DojoAPI, tmp_path: Path):
    dest = tmp_path / "occupied"
    dest.mkdir()
    (dest / "keep-me.txt").write_text("user data", encoding="utf-8")
    with pytest.raises(ValueError, match="not empty"):
        export_store(populated.store, dest)
    assert (dest / "keep-me.txt").exists()


def test_export_refuses_self(populated: DojoAPI):
    with pytest.raises(ValueError, match="source store itself"):
        export_store(populated.store, populated.store.dojo_dir)


def test_export_cli_envelope(populated: DojoAPI, tmp_path: Path, capsys):
    dest = tmp_path / "cli-export"
    rc = main(["--db", str(populated.store.dojo_dir), "export", str(dest)])
    data = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0 and data["ok"]
    assert data["counts"]["campaigns"] == 1
    assert "doctor" in data["next"], "envelope teaches how to verify the export"
