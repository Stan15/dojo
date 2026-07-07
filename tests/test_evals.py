"""Tier-2 prompt evals (ADR 016): real-model compliance against the scenario
corpus, ratcheted per-model baselines.

Run:  DOJO_EVAL_FULFILLER="codex exec" python -m pytest -m eval -q
      (optional: DOJO_EVAL_SAMPLES=3 for stability)

Fulfiller-agnostic by construction: any command taking the prompt on stdin and
printing the result (JSON anywhere in stdout) qualifies. Scoring is fully
deterministic — the same validators/appliers production uses. Without a
fulfiller configured these tests SKIP loudly; they never silently pass.

Baselines: evals/baselines/<slug>.json is the committed floor for that
fulfiller. A run below its floor fails; a better run should update the baseline
in the same commit as the prompt change that earned it. Reports for human
review land in evals/reports/ (gitignored).
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from dojo.schemas import Attempt, Campaign, Exercise, Insight
from dojo.store import DojoStore
from dojo.tasks import compiler, service

pytestmark = pytest.mark.eval

EVALS_DIR = Path(__file__).parent.parent / "evals"
SCENARIOS = sorted((EVALS_DIR / "scenarios").glob("*.yaml"))

FULFILLER = os.environ.get("DOJO_EVAL_FULFILLER", "").strip()
SAMPLES = int(os.environ.get("DOJO_EVAL_SAMPLES", "1"))
TIMEOUT = int(os.environ.get("DOJO_EVAL_TIMEOUT", "300"))


def slug_for(command: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", command.lower()).strip("-")[:40]


def seed_store(tmp_path: Path, seed: dict) -> DojoStore:
    store = DojoStore(tmp_path / "dojo")
    camp = Campaign(**seed["campaign"])
    store.campaigns.save(camp)
    for ins in seed.get("insights", []):
        store.insights.save(camp.id, Insight(**ins))
    if "exercise" in seed:
        store.exercises.save(camp.id, Exercise(**seed["exercise"]))
    for att in seed.get("attempts", []):
        store.attempts.save(camp.id, Attempt(**{"campaign_id": camp.id, **att}))
    return store


def compile_scenario(store: DojoStore, scenario: dict):
    camp = store.campaigns.get(scenario["seed"]["campaign"]["id"])
    args = dict(scenario["compile"])
    fn = args.pop("fn")
    if fn == "generate":
        return compiler.compile_generate(store, camp, **args)
    if fn == "diagnostic":
        return compiler.compile_diagnostic(store, camp, **args)
    if fn == "grade":
        attempt = store.attempts.get(camp.id, args.pop("attempt_id"))
        exercise = store.exercises.get(camp.id, attempt.exercise_id)
        return compiler.compile_grade(
            store, camp, exercise,
            attempt_id=attempt.id, user_answer=attempt.user_answer,
        )
    raise ValueError(f"unknown compile fn: {fn}")


def run_fulfiller(prompt: str) -> str:
    proc = subprocess.run(
        shlex.split(FULFILLER), input=prompt,
        capture_output=True, text=True, timeout=TIMEOUT,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"fulfiller exited {proc.returncode}: {proc.stderr[:300]}")
    return proc.stdout


def quality_score(scenario: dict, store: DojoStore, outcome) -> dict:
    """Deterministic quality signals beyond compliance — recorded, not gating."""
    checks = scenario.get("quality_checks") or {}
    signals: dict[str, bool | float | None] = {}
    if "any_item_mentions" in checks and outcome.ok and outcome.applied:
        camp_id = scenario["seed"]["campaign"]["id"]
        texts = " ".join(
            (c.prompt or "") + " " + (c.answer or "")
            for c in store.candidates.list(camp_id)
        ).lower()
        signals["mentions_target"] = any(w.lower() in texts for w in checks["any_item_mentions"])
    if "expected_score_band" in checks and outcome.ok and outcome.applied:
        got = outcome.applied.get("score")
        lo, hi = checks["expected_score_band"]
        signals["score_in_expected_band"] = got is not None and lo <= got <= hi
    return signals


@pytest.fixture(scope="session")
def scorecard():
    if not FULFILLER:
        pytest.skip("DOJO_EVAL_FULFILLER not set — evals skipped (never silently passed)")
    card = {
        "command": FULFILLER,
        "date": datetime.now(timezone.utc).isoformat(),
        "samples": SAMPLES,
        "scenarios": {},
    }
    yield card
    scores = card["scenarios"]
    if not scores:
        return
    card["mean_compliance"] = sum(s["compliance"] for s in scores.values()) / len(scores)
    reports = EVALS_DIR / "reports"
    reports.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    (reports / f"{slug_for(FULFILLER)}-{stamp}.json").write_text(
        json.dumps(card, indent=2), encoding="utf-8"
    )
    baseline_file = EVALS_DIR / "baselines" / f"{slug_for(FULFILLER)}.json"
    if not baseline_file.exists():
        baseline_file.parent.mkdir(exist_ok=True)
        baseline_file.write_text(json.dumps(card, indent=2), encoding="utf-8")


@pytest.mark.parametrize("scenario_path", SCENARIOS, ids=lambda p: p.stem)
def test_scenario_compliance_meets_baseline(scenario_path: Path, tmp_path: Path, scorecard):
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    ok_count, errors, signals = 0, [], {}
    for sample in range(SAMPLES):
        store = seed_store(tmp_path / f"s{sample}", scenario["seed"])
        compiled = compile_scenario(store, scenario)
        task = service.emit(store, compiled)
        raw = run_fulfiller(task.prompt)
        outcome = service.submit(store, task.id, raw)
        ok_count += outcome.ok
        if not outcome.ok:
            errors.extend(outcome.errors[:3])
        else:
            signals = quality_score(scenario, store, outcome)

    compliance = ok_count / SAMPLES
    scorecard["scenarios"][scenario_path.stem] = {
        "compliance": compliance,
        "quality_signals": signals,
        "errors": errors[:6],
    }

    baseline_file = EVALS_DIR / "baselines" / f"{slug_for(FULFILLER)}.json"
    if baseline_file.exists():
        baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
        floor = baseline["scenarios"].get(scenario_path.stem, {}).get("compliance", 0.0)
        assert compliance >= floor, (
            f"{scenario_path.stem}: compliance {compliance} fell below the committed "
            f"baseline {floor} for {FULFILLER!r} — the prompt change regressed. "
            f"Errors: {errors[:3]}"
        )
    else:
        # Bootstrap run: report + baseline are written by the scorecard fixture.
        assert compliance > 0.0, (
            f"{scenario_path.stem}: fulfiller produced zero compliant responses on "
            f"the bootstrap run; not writing a zero baseline. Errors: {errors[:3]}"
        )
