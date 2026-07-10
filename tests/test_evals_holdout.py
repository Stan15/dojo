"""HOLDOUT prompt evals — the anti-reward-hacking gate (owner directive
2026-07-09).

Prompt iteration reads the visible corpus's verdicts and traces; a prompt can
therefore learn THE TEST instead of the skill. This tier measures
generalization: same machinery as tests/test_evals_quality.py, but under a
protocol that keeps it out of the iteration loop.

THE PROTOCOL (breaking it silently voids what this tier measures):
1. NEVER during prompt iteration: don't run this tier, don't read its
   scenario files, verdicts, or traces while tuning prompts.
2. Run at RELEASE GATES only (before a version tag, after an iteration
   series):
       DOJO_EVAL_DRIVER="codex exec ..." python -m pytest -m eval_holdout -q
3. A holdout run yields ONE consumable bit: the aggregate gap vs the
   visible mean. It may tell you THAT the prompts overfit — NEVER what to
   change (owner ruling, absolute). Bad gap → return to the VISIBLE corpus,
   broaden it with new visible scenarios authored without holdout
   knowledge, iterate there, re-run holdout later.
4. MECHANICAL ENFORCEMENT: this module strips verdicts, judge output, and
   all traces before anything touches disk — per-scenario floors (bare
   scores) are the only detail persisted, because the ratchet needs them.
   The data you must never optimize on is never written.
5. If a holdout scenario's data is ever consumed anyway, it is burnt:
   move it to corpus/quality/ and have a SUBAGENT author a fresh blind
   replacement.
6. Holdout scenarios are authored by a subagent and committed unread by the
   prompt author; the shape suite (tests/test_quality_corpus.py) and the
   judge calibration gate are their mechanical QA.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from dojo.evals.runner import (
    CORPUS_DIR,
    ComplianceFailure,
    calibration_gate,
    execute_quality_scenario,
    judge_output,
    merge_holdout_baseline,
    slug_for,
)

EVALS_DIR = Path(__file__).parent.parent / "evals"

pytestmark = pytest.mark.eval_holdout

SCENARIOS = sorted((CORPUS_DIR / "holdout").glob("*.yaml"))

DRIVER = os.environ.get("DOJO_EVAL_DRIVER", "").strip()
JUDGE = os.environ.get("DOJO_EVAL_JUDGE", "").strip() or DRIVER
TIMEOUT = int(os.environ.get("DOJO_EVAL_TIMEOUT", "300"))
MARGIN = float(os.environ.get("DOJO_EVAL_MARGIN", "0.10"))


def pair_slug() -> str:
    return f"{slug_for(DRIVER)}__{slug_for(JUDGE)}"


@pytest.fixture(scope="session")
def holdout_card():
    if not DRIVER:
        pytest.skip("DOJO_EVAL_DRIVER not set — holdout evals skipped (never silently passed)")
    card = {
        "driver": DRIVER,
        "judge": JUDGE,
        "tier": "holdout",
        "date": datetime.now(timezone.utc).isoformat(),
        "margin": MARGIN,
        "scenarios": {},
    }
    yield card
    if not card["scenarios"]:
        return
    card["mean_quality"] = sum(s["quality"] for s in card["scenarios"].values()) / len(card["scenarios"])
    # THE one consumable bit, computed for you: the gap vs the committed
    # visible-pair baseline. Small gap = prompts generalize; large gap =
    # they overfit the visible corpus (broaden it; never read holdout).
    visible_file = EVALS_DIR / "baselines" / f"{pair_slug()}.json"
    if visible_file.exists():
        visible = json.loads(visible_file.read_text(encoding="utf-8"))
        card["visible_mean"] = visible.get("mean_quality")
        if card["visible_mean"] is not None:
            card["generalization_gap"] = round(card["visible_mean"] - card["mean_quality"], 3)
    print(f"\nHOLDOUT GATE: holdout mean {card['mean_quality']:.3f}"
          + (f" · visible mean {card['visible_mean']:.3f} · gap {card['generalization_gap']:+.3f}"
             if card.get("visible_mean") is not None else " · (no visible baseline to compare)"))
    reports = EVALS_DIR / "reports"
    reports.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    (reports / f"holdout-{pair_slug()}-{stamp}.json").write_text(
        json.dumps(card, indent=2), encoding="utf-8"
    )
    # Ratchet-safe write: refused zeros never become floors; scenarios the
    # baseline doesn't know yet (burnt-and-replaced, or refused last gate)
    # bootstrap into it; existing floors are never touched here.
    merge_holdout_baseline(card, EVALS_DIR / "baselines" / f"{pair_slug()}__holdout.json")


@pytest.mark.parametrize("scenario_path", SCENARIOS, ids=lambda p: p.stem)
def test_holdout_quality_meets_baseline(scenario_path: Path, tmp_path: Path, holdout_card):
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    criteria = scenario["judge_rubric"]
    context = scenario["scenario_context"].strip()

    problem = calibration_gate(JUDGE, context, scenario["references"], criteria, TIMEOUT)
    if problem:
        pytest.fail(f"{scenario_path.stem}: {problem}")

    trace_log: list = []
    try:
        output_text = execute_quality_scenario(
            scenario, tmp_path, DRIVER, TIMEOUT, trace_log=trace_log)
    except ComplianceFailure as e:
        # Error strings only — no traces (protocol rule 4). A failing holdout
        # scenario gets burnt (migrated to visible) before anyone triages it.
        holdout_card.setdefault("failures", {})[scenario_path.stem] = {
            "errors": e.errors[:3],
        }
        pytest.fail("holdout: driver failed compliance (details withheld — "
                    "burn the scenario per protocol rule 5 before triaging)")
    result = judge_output(JUDGE, context, output_text, criteria, TIMEOUT)

    # Bare score only (protocol rule 4): verdicts, judge output, and traces
    # are deliberately NOT persisted for holdout — optimizing on them would
    # void the tier, so they never reach disk.
    holdout_card["scenarios"][scenario_path.stem] = {
        "quality": result["score"],
    }

    baseline_file = EVALS_DIR / "baselines" / f"{pair_slug()}__holdout.json"
    if baseline_file.exists():
        baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
        floor = baseline["scenarios"].get(scenario_path.stem, {}).get("quality", 0.0)
        margin = baseline.get("margin", MARGIN)
        assert result["score"] >= floor - margin, (
            f"{scenario_path.stem}: holdout quality {result['score']:.2f} fell below "
            f"baseline {floor:.2f} − margin {margin:.2f} — the prompts may have "
            "overfit the visible corpus. Do NOT read this scenario's data: return "
            "to the visible corpus, broaden it, iterate there (owner ruling)."
        )
    else:
        assert result["score"] > 0.0, (
            f"{scenario_path.stem}: zero quality on the holdout bootstrap; refusing a zero baseline."
        )
