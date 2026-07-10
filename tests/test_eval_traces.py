"""Eval-run driver traces (owner directive 2026-07-09): the model's raw
output — its thinking, not just its JSON — rides in the local report beside
the ratchet score, so prompt iteration reads WHY a scenario scored what it
did. Committed baselines stay lean: floors only, traces stripped.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dojo.evals.runner import (
    ComplianceFailure,
    execute_quality_scenario,
    fulfill_step,
    lean_baseline,
    merge_holdout_baseline,
    seed_store,
)
from dojo.tasks import compiler

CAMP = {"id": "tr", "name": "Traces", "mission": "Prove provenance."}


def scripted(tmp_path: Path, stdout: str) -> str:
    script = tmp_path / "driver.py"
    script.write_text(
        "import sys\nsys.stdin.read()\n" f"sys.stdout.write({stdout!r})\n",
        encoding="utf-8",
    )
    return f"python {script}"


GOOD = ("Thinking out loud: the learner needs one opener drill.\n"
        + json.dumps({"items": [{"prompt": "Open a chat in French.",
                                 "answer": "Bonjour !", "rubric": "- greets",
                                 "skill": "produce"}], "note": None}))


def test_fulfill_step_returns_the_raw_driver_output(tmp_path: Path):
    store = seed_store(tmp_path, {"campaign": CAMP})
    compiled = compiler.compile_generate(
        store, store.campaigns.get("tr"), topic_path="t.a", n_items=1,
        difficulty="beginner")
    outcome, extracted, counts, raw = fulfill_step(
        store, compiled, scripted(tmp_path, GOOD), timeout=30)
    assert outcome.ok
    assert "Thinking out loud" in raw, "prose around the JSON is the point"
    assert "Thinking out loud" not in extracted, "extracted stays pure JSON"


def test_quality_scenario_fills_the_trace_log(tmp_path: Path):
    scenario = {
        "seed": {"campaign": CAMP},
        "steps": [{"compile": {"fn": "generate", "topic_path": "t.a",
                               "n_items": 1, "difficulty": "beginner"}}],
    }
    trace_log: list = []
    out = execute_quality_scenario(
        scenario, tmp_path, scripted(tmp_path, GOOD), 30, trace_log=trace_log)
    assert '"items"' in out
    assert len(trace_log) == 1 and trace_log[0]["ok"] is True
    assert trace_log[0]["kind"] == "exercise.generate"
    assert "Thinking out loud" in trace_log[0]["raw"]
    assert "drafting practice exercises" in trace_log[0]["prompt"], \
        "the report snapshot carries what was ASKED, not just what came back"


def test_rejected_step_raises_with_the_raw_attached(tmp_path: Path):
    scenario = {
        "seed": {"campaign": CAMP},
        "steps": [{"compile": {"fn": "generate", "topic_path": "t.a",
                               "n_items": 1, "difficulty": "beginner"}}],
    }
    trace_log: list = []
    bad = "I refuse to answer in the requested format. Sorry!"
    with pytest.raises(ComplianceFailure) as exc:
        execute_quality_scenario(
            scenario, tmp_path, scripted(tmp_path, bad), 30, trace_log=trace_log)
    assert exc.value.raw and "refuse" in exc.value.raw
    assert trace_log and trace_log[0]["ok"] is False and trace_log[0]["errors"]


def test_lean_baseline_strips_traces_but_keeps_floors():
    card = {
        "driver": "x", "margin": 0.1, "mean_quality": 0.8,
        "failures": {"broken_scenario": {"errors": ["boom"], "driver_trace": []}},
        "scenarios": {
            "s1": {"quality": 0.8, "verdicts": {"c1": "pass"},
                   "judged_output": "{…}", "judge_trace": "judge prose",
                   "driver_trace": [{"ok": True, "raw": "huge model prose…"}]},
        },
    }
    lean = lean_baseline(card)
    assert lean["scenarios"]["s1"] == {"quality": 0.8, "verdicts": {"c1": "pass"}}
    assert "failures" not in lean
    for key in ("driver_trace", "judge_trace", "judged_output"):
        assert key not in json.dumps(lean), key
    assert card["scenarios"]["s1"]["driver_trace"], "the report copy keeps the trace"


class TestMergeHoldoutBaseline:
    """The holdout ratchet's write rules, learned at the first live gate
    (2026-07-09): a refused zero must never become a floor, later gates
    bootstrap scenarios the baseline doesn't know, and existing floors are
    never rewritten."""

    CARD = {"driver": "d", "judge": "j", "tier": "holdout", "margin": 0.1,
            "scenarios": {"good": {"quality": 0.8}, "refused": {"quality": 0.0}}}

    def test_bootstrap_excludes_refused_zeros(self, tmp_path: Path):
        f = tmp_path / "b.json"
        assert merge_holdout_baseline(self.CARD, f) == "bootstrapped"
        floors = json.loads(f.read_text())["scenarios"]
        assert floors == {"good": {"quality": 0.8}}, "a zero floor breaks the ratchet forever"

    def test_later_gate_bootstraps_only_unknown_scenarios(self, tmp_path: Path):
        f = tmp_path / "b.json"
        f.write_text(json.dumps({"scenarios": {"good": {"quality": 0.9}}}))
        card = {"scenarios": {"good": {"quality": 0.2}, "replacement": {"quality": 0.7}}}
        assert merge_holdout_baseline(card, f) == "merged 1"
        floors = json.loads(f.read_text())["scenarios"]
        assert floors["good"] == {"quality": 0.9}, "existing floors are never rewritten"
        assert floors["replacement"] == {"quality": 0.7}

    def test_all_zero_card_changes_nothing(self, tmp_path: Path):
        f = tmp_path / "b.json"
        assert merge_holdout_baseline({"scenarios": {"r": {"quality": 0.0}}}, f) == "unchanged"
        assert not f.exists()


class TestHoldoutStructuralIsolation:
    """Owner ruling (2026-07-09): holdout data must never optimize prompts —
    enforced STRUCTURALLY: normal benchmark tiers never load the holdout
    corpus, and the holdout gate's report physically contains nothing but
    aggregates."""

    def test_normal_benchmark_never_loads_holdout(self, tmp_path, monkeypatch):
        from dojo.evals import runner
        loaded: list[str] = []
        real = runner.load_corpus
        monkeypatch.setattr(runner, "load_corpus", lambda tier: (loaded.append(tier), real(tier))[1])
        runner.run_benchmark(
            driver="false", judge="false", workdir=tmp_path,
            tiers=("compliance", "quality"),
        )
        assert "holdout" not in loaded, "the iteration workflow must be blind to holdout"

    def test_holdout_gate_report_is_aggregate_only(self, tmp_path):
        from dojo.evals.runner import run_holdout_gate
        gate = run_holdout_gate(driver="false", judge="false", workdir=tmp_path, timeout=5)
        dumped = json.dumps(gate)
        assert "scenarios" in gate and isinstance(gate["scenarios"], int), \
            "scenario COUNT only — never a list"
        for forbidden in ("verdicts", "driver_trace", "judge_trace", "judged_output",
                          "raw", "prompt"):
            assert forbidden not in dumped, forbidden
        assert "holdout_" not in dumped, "no scenario names in the report"
