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
        assert rc == 1 and "model.command" in data["error"]


class TestBenchmarkCli:
    def test_compliance_benchmark_with_scripted_model(self, dojo_dir: Path, tmp_path: Path, capsys):
        """A scripted driver that always answers with one fixed generate payload:
        generate scenarios pass, the grade scenario fails its schema — the report
        must show both, grouped by category, without crashing or lying."""
        script = tmp_path / "scripted_model.py"
        script.write_text(
            "import sys\nsys.stdin.read()\n"
            "print('''{\"items\": [\n"
            "  {\"prompt\": \"Translate: the cat sleeps.\", \"answer\": \"Le chat dort.\","
            "   \"rubric\": \"- correct verb\", \"skill\": \"produce\"},\n"
            "  {\"prompt\": \"Translate: the dog eats.\", \"answer\": \"Le chien mange.\","
            "   \"rubric\": \"- correct verb\", \"skill\": \"produce\"},\n"
            "  {\"prompt\": \"Translate: I am here.\", \"answer\": \"Je suis ici.\","
            "   \"rubric\": \"- correct verb\", \"skill\": \"produce\"}\n"
            "], \"note\": null, \"intervention\": null}''')\n",
            encoding="utf-8",
        )
        out_file = tmp_path / "report.json"
        rc, report = run(
            capsys, "--db", str(dojo_dir), "--json", "benchmark",
            "--driver", f"python {script}", "--tier", "compliance",
            "--output", str(out_file),
        )
        assert rc == 0
        assert report["total_scenarios"] == 4
        assert "contract-compliance" in report["categories"]
        scores = {
            s["name"]: s["score"]
            for s in report["categories"]["contract-compliance"]["scenarios"]
        }
        assert scores["generate_grounded_french.yaml".removesuffix(".yaml")] == 1.0
        assert scores["grade_partial_credit"] == 0.0, "wrong-shape output must fail honestly"
        assert out_file.exists()

    def test_configured_judge_wins_over_self_judging(self, dojo_dir: Path, tmp_path: Path, capsys):
        """benchmark.judge config supplies the standing judge (owner feature
        2026-07-11): omitting -j must not silently mean self-judging once a
        judge is configured; an explicit -j still wins."""
        from unittest.mock import patch

        run(capsys, "--db", str(dojo_dir), "--json", "config", "set",
            "benchmark.judge", "echo CONFIGURED-JUDGE")
        captured = {}

        def fake_run_benchmark(driver, judge, **kw):
            captured["judge"] = judge
            return {"driver": driver, "judge": judge, "pair": "p", "date": "",
                    "total_scenarios": 0, "categories": {}, "failures": {}}

        with patch("dojo.cli.run_benchmark", side_effect=fake_run_benchmark, create=True), \
             patch("dojo.evals.runner.run_benchmark", side_effect=fake_run_benchmark):
            run(capsys, "--db", str(dojo_dir), "--json", "benchmark",
                "--driver", "echo DRIVER", "--tier", "compliance",
                "--output", str(tmp_path / "r.json"))
        assert captured["judge"] == "echo CONFIGURED-JUDGE"

        with patch("dojo.cli.run_benchmark", side_effect=fake_run_benchmark, create=True), \
             patch("dojo.evals.runner.run_benchmark", side_effect=fake_run_benchmark):
            run(capsys, "--db", str(dojo_dir), "--json", "benchmark",
                "--driver", "echo DRIVER", "--judge", "echo EXPLICIT",
                "--tier", "compliance", "--output", str(tmp_path / "r2.json"))
        assert captured["judge"] == "echo EXPLICIT"


class TestBenchmarkQualityPipeline:
    """CI lock on the FULL quality tier of run_benchmark with scripted models —
    no LLM, pure plumbing. A signature mismatch between run_benchmark and
    execute_quality_scenario shipped to a real user because nothing drove this
    path in CI; the only failure mode allowed here is the judge's own
    calibration refusal, and the report must degrade honestly (I10)."""

    def test_quality_tier_degrades_honestly_with_uncalibrated_judge(self, tmp_path: Path):
        import tempfile

        from dojo.evals.runner import load_corpus, run_benchmark

        driver = tmp_path / "driver.py"
        driver.write_text("import sys\nsys.stdin.read()\nprint('{}')\n", encoding="utf-8")
        judge = tmp_path / "judge.py"
        judge.write_text(
            "import sys, json, re\n"
            "prompt = sys.stdin.read()\n"
            "ids = re.findall(r'^(c\\d+):', prompt.split('## RUBRIC')[-1], re.M)\n"
            "print(json.dumps({'verdicts': [{'id': i, 'verdict': 'fail', 'why': 'scripted'} for i in ids]}))\n",
            encoding="utf-8",
        )
        with tempfile.TemporaryDirectory() as workdir:
            report = run_benchmark(
                driver=f"python {driver}", judge=f"python {judge}",
                workdir=Path(workdir), tiers=("quality",),
            )

        n_quality = len(load_corpus("quality"))
        assert report["total_scenarios"] == n_quality
        assert report["errors"] == n_quality, "all-fail judge cannot rank good>bad → every scenario errors"
        assert report["overall"] is None and report["scored_scenarios"] == 0
        for cat in report["categories"].values():
            assert cat["mean"] is None and cat["errors"] > 0
            for sc in cat["scenarios"]:
                assert "calibration" in (sc["error"] or ""), (
                    f"only calibration refusal is an acceptable failure here, got: {sc['error']}"
                )


    def test_benchmark_never_touches_the_user_store(self, dojo_dir: Path, tmp_path: Path, capsys):
        """Owner concern: benchmarks must run entirely in throwaway stores.
        The user's --db store must be byte-identical afterwards."""
        import hashlib

        def store_hash() -> str:
            h = hashlib.sha256()
            for p in sorted(dojo_dir.rglob("*")):
                if p.is_file() and ".git" not in p.parts:
                    h.update(str(p.relative_to(dojo_dir)).encode())
                    h.update(p.read_bytes())
            return h.hexdigest()

        emit_task(dojo_dir)  # give the store real content worth protecting
        before = store_hash()

        script = tmp_path / "scripted_model.py"
        script.write_text("import sys\nsys.stdin.read()\nprint('{}')\n", encoding="utf-8")
        run(capsys, "--db", str(dojo_dir), "--json", "benchmark",
            "--driver", f"python {script}", "--tier", "compliance",
            "--output", str(tmp_path / "r.json"))

        assert store_hash() == before, "benchmark leaked writes into the user's store"


class TestModelCommandNaming:
    """`model.command` is the user-facing key (owner ruling 2026-07-09:
    'fulfiller' is contract jargon); `fulfiller.command` keeps working for
    existing installs."""

    def test_legacy_fulfiller_command_still_honored(self, dojo_dir: Path, capsys):
        task_id = emit_task(dojo_dir)
        store = DojoStore(dojo_dir)
        store.configs.set_value("fulfiller.command", f"python -c \"import sys; sys.stdin.read(); print('{VALID_ONE_ITEM}'.replace(chr(39), chr(34)))\"")
        # a legacy-configured store must still drain tasks
        from dojo.interactive import fulfiller_command
        from dojo.api import DojoAPI
        assert fulfiller_command(DojoAPI(dojo_dir)) is not None

    def test_model_command_takes_precedence(self, dojo_dir: Path):
        store = DojoStore(dojo_dir)
        store.configs.set_value("fulfiller.command", "old-cmd")
        store.configs.set_value("model.command", "new-cmd")
        from dojo.interactive import fulfiller_command
        from dojo.api import DojoAPI
        assert fulfiller_command(DojoAPI(dojo_dir)) == "new-cmd"
