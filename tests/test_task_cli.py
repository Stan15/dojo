"""CLI task surface tests: list/show/submit round-trip and the one-string
fulfiller runner (QUESTIONS.md Q1 — prompt on stdin, JSON on stdout, same
validated submit path as every other fulfiller)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dojo.cli import main
from dojo.schemas import Campaign
from dojo.store import DojoStore
from dojo.tasks import compiler, service

CAMP_ID = "cli-camp"


@pytest.fixture
def dojo_dir(tmp_path: Path) -> Path:
    d = tmp_path / "dojo"
    store = DojoStore(d)
    store.campaigns.save(Campaign(id=CAMP_ID, name="CLI", mission="Test the CLI."))
    return d


def emit_task(dojo_dir: Path, n_items: int = 1) -> str:
    store = DojoStore(dojo_dir)
    compiled = compiler.compile_generate(
        store, store.campaigns.get(CAMP_ID),
        topic_path="t.cli", n_items=n_items, difficulty="beginner",
    )
    return service.emit(store, compiled).id


VALID_ONE_ITEM = json.dumps({
    "items": [{"prompt": "Name the CLI under test.", "answer": "dojo",
               "rubric": "- says dojo", "skill": "recall"}],
    "note": None,
})


def run(capsys, *argv: str) -> tuple[int, dict]:
    rc = main(list(argv))
    out = capsys.readouterr().out.strip().splitlines()[-1]
    return rc, json.loads(out)


class TestTaskCli:
    def test_list_shows_pending_with_next_hint(self, dojo_dir: Path, capsys):
        task_id = emit_task(dojo_dir)
        rc, data = run(capsys, "--db", str(dojo_dir), "task", "list", "--status", "pending")
        assert rc == 0
        assert [t["id"] for t in data["tasks"]] == [task_id]
        assert "dojo task submit" in data["next"]

    def test_show_prompt_prints_bare_payload(self, dojo_dir: Path, capsys):
        task_id = emit_task(dojo_dir)
        rc = main(["--db", str(dojo_dir), "task", "show", task_id, "--prompt"])
        out = capsys.readouterr().out
        assert rc == 0
        assert out.startswith("You are drafting practice exercises")
        assert "{{" not in out

    def test_submit_from_file_applies(self, dojo_dir: Path, tmp_path: Path, capsys):
        task_id = emit_task(dojo_dir)
        result_file = tmp_path / "result.json"
        result_file.write_text(VALID_ONE_ITEM, encoding="utf-8")
        rc, data = run(capsys, "--db", str(dojo_dir), "task", "submit", task_id,
                       "--file", str(result_file))
        assert rc == 0 and data["ok"] and data["status"] == "fulfilled"
        assert len(DojoStore(dojo_dir).candidates.list(CAMP_ID)) == 1

    def test_submit_invalid_reports_actionable_errors(self, dojo_dir: Path, tmp_path: Path, capsys):
        task_id = emit_task(dojo_dir)
        bad = tmp_path / "bad.json"
        bad.write_text('{"items": []}', encoding="utf-8")
        rc, data = run(capsys, "--db", str(dojo_dir), "task", "submit", task_id, "--file", str(bad))
        assert rc == 1 and not data["ok"]
        assert data["errors"] and "resubmit" in data["next"]

    def test_run_drains_queue_through_one_string_command(self, dojo_dir: Path, capsys):
        emit_task(dojo_dir)
        # a tiny script file avoids shell-quoting games in the one-string command
        script = dojo_dir.parent / "fake_fulfiller.py"
        script.write_text(
            "import sys\n"
            "sys.stdin.read()\n"
            f"print({VALID_ONE_ITEM!r})\n",
            encoding="utf-8",
        )
        rc, data = run(capsys, "--db", str(dojo_dir), "task", "run",
                       "--command", f"python {script}")
        assert rc == 0, data
        assert data["fulfilled"] == 1 and data["attempted"] == 1
        assert len(DojoStore(dojo_dir).candidates.list(CAMP_ID)) == 1

    def test_run_without_command_config_fails_honestly(self, dojo_dir: Path, capsys):
        emit_task(dojo_dir)
        rc, data = run(capsys, "--db", str(dojo_dir), "task", "run")
        assert rc == 1 and "fulfiller.command" in data["error"]
