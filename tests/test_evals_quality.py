"""Tier-3 evals: judged pedagogical quality (ADR 016 §Tier 3).

Run:  DOJO_EVAL_FULFILLER="codex exec ..." python -m pytest -m eval -q tests/test_evals_quality.py
      (judge defaults to the driver; override with DOJO_EVAL_JUDGE="<cmd>")

What makes this reliable rather than vibes:
  - binary rubric criteria with weights, never scales;
  - every "pass" requires a verbatim quote from the judged output, checked
    mechanically — unproven passes are discarded as judge failures;
  - a calibration gate: the judge must rank a planted good reference above a
    planted bad one, blind, or the run is refused ("judge unreliable"), never
    averaged into scores;
  - baselines are keyed on the (driver, judge) pair and ratcheted with the
    recorded margin, so a prompt tweak yields a readable verdict.

Scenario chains (steps) test the learning loop itself: a scripted reflection
is applied, then generation runs — the rubric asks whether generation visibly
used what reflection learned.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from evals_lib import (
    EVALS_DIR,
    calibration_gate,
    compile_step,
    fulfill_step,
    judge_output,
    seed_store,
    slug_for,
    submit_canned,
)

pytestmark = pytest.mark.eval

SCENARIOS = sorted((EVALS_DIR / "scenarios" / "quality").glob("*.yaml"))

DRIVER = os.environ.get("DOJO_EVAL_FULFILLER", "").strip()
JUDGE = os.environ.get("DOJO_EVAL_JUDGE", "").strip() or DRIVER
TIMEOUT = int(os.environ.get("DOJO_EVAL_TIMEOUT", "300"))
MARGIN = float(os.environ.get("DOJO_EVAL_MARGIN", "0.10"))


def pair_slug() -> str:
    return f"{slug_for(DRIVER)}__{slug_for(JUDGE)}"


@pytest.fixture(scope="session")
def quality_card():
    if not DRIVER:
        pytest.skip("DOJO_EVAL_FULFILLER not set — quality evals skipped (never silently passed)")
    card = {
        "driver": DRIVER,
        "judge": JUDGE,
        "date": datetime.now(timezone.utc).isoformat(),
        "margin": MARGIN,
        "scenarios": {},
    }
    yield card
    if not card["scenarios"]:
        return
    card["mean_quality"] = sum(s["quality"] for s in card["scenarios"].values()) / len(card["scenarios"])
    reports = EVALS_DIR / "reports"
    reports.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    (reports / f"quality-{pair_slug()}-{stamp}.json").write_text(
        json.dumps(card, indent=2), encoding="utf-8"
    )
    baseline_file = EVALS_DIR / "baselines" / f"{pair_slug()}.json"
    if not baseline_file.exists():
        baseline_file.parent.mkdir(exist_ok=True)
        baseline_file.write_text(json.dumps(card, indent=2), encoding="utf-8")


def execute_scenario(scenario: dict, tmp_path: Path) -> str:
    """Runs the scenario's steps; returns the final step's extracted output
    (the thing on trial). Chain steps with `respond_with` are scripted so the
    judged step is isolated from upstream model variance."""
    store = seed_store(tmp_path, scenario["seed"])
    campaign_id = scenario["seed"]["campaign"]["id"]
    final_output = None
    for step in scenario["steps"]:
        compiled = compile_step(store, campaign_id, step["compile"])
        if "respond_with" in step:
            outcome = submit_canned(store, compiled, step["respond_with"])
            assert outcome.ok, f"scripted step rejected: {outcome.errors}"
            final_output = json.dumps(step["respond_with"], indent=1)
        else:
            outcome, extracted = fulfill_step(store, compiled, DRIVER, TIMEOUT)
            if not outcome.ok:
                pytest.fail(
                    f"driver failed compliance inside a quality scenario "
                    f"(fix Tier 2 first): {outcome.errors[:3]}"
                )
            final_output = extracted
    assert final_output is not None
    return final_output


@pytest.mark.parametrize("scenario_path", SCENARIOS, ids=lambda p: p.stem)
def test_pedagogical_quality_meets_baseline(scenario_path: Path, tmp_path: Path, quality_card):
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    criteria = scenario["judge_rubric"]
    context = scenario["scenario_context"].strip()

    # 1. Refuse an uncalibrated judge — noise is rejected, not averaged (T3.3).
    problem = calibration_gate(JUDGE, context, scenario["references"], criteria, TIMEOUT)
    if problem:
        pytest.fail(f"{scenario_path.stem}: {problem}")

    # 2. Drive the system for real; judge the final output.
    output_text = execute_scenario(scenario, tmp_path)
    result = judge_output(JUDGE, context, output_text, criteria, TIMEOUT)

    quality_card["scenarios"][scenario_path.stem] = {
        "quality": result["score"],
        "verdicts": result["verdicts"],
        "discarded": result["discarded"],
    }

    # 3. Ratchet against the committed (driver, judge) baseline.
    baseline_file = EVALS_DIR / "baselines" / f"{pair_slug()}.json"
    if baseline_file.exists():
        baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
        floor = baseline["scenarios"].get(scenario_path.stem, {}).get("quality", 0.0)
        margin = baseline.get("margin", MARGIN)
        assert result["score"] >= floor - margin, (
            f"{scenario_path.stem}: quality {result['score']:.2f} fell below baseline "
            f"{floor:.2f} − margin {margin:.2f} for pair {pair_slug()!r}. "
            f"Verdicts: {result['verdicts']}"
        )
    else:
        assert result["score"] > 0.0, (
            f"{scenario_path.stem}: zero quality on the bootstrap run; refusing a zero "
            f"baseline. Verdicts: {result['verdicts']}"
        )
