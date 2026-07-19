"""SKILL.md behavioral evals (owner-approved 2026-07-18; design:
docs/design/skill-behavioral-evals.md).

Two layers here:
- FREE (default suite): scenario integrity (shape, known checks, judgeable
  rubrics) and harness plumbing proven with SCRIPTED drivers — no model, no
  spend, real store/check machinery.
- `-m eval_skill` (spend): a real driver agent (DOJO_SKILL_DRIVER) operates
  each sandboxed scenario; deterministic check scores ratchet per driver in
  evals/baselines/<driver>__skill.json. Judged-rubric floors bootstrap in a
  later owner-authorized spend (design §Recommendation).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dojo.evals.skill_runner import (
    CHECKS, SKILL_CORPUS, driver_prompt, load_skill_corpus, run_skill_scenario,
)
from dojo.evals.runner import slug_for

SCENARIOS = load_skill_corpus()
BASELINES = Path(__file__).parent.parent / "evals" / "baselines"
REPORTS = Path(__file__).parent.parent / "evals" / "reports"
MARGIN = 0.15  # agentic multi-step variance is strictly higher than single-call


class TestSkillCorpusIntegrity:
    """Free: the scenarios themselves can never rot."""

    def test_battery_exists(self):
        assert len(SCENARIOS) >= 6, "the v1 battery is six scenarios"

    @pytest.mark.parametrize("sc", SCENARIOS, ids=lambda s: s["name"])
    def test_shape(self, sc):
        assert sc["user_message"].strip()
        assert sc["checks"], "a scenario without checks judges nothing"
        for spec in sc["checks"]:
            name = spec if isinstance(spec, str) else spec["check"]
            assert name in CHECKS, f"unknown check {name!r}"
        for c in sc.get("judge_rubric", []):
            assert c["question"].strip().endswith("?")

    @pytest.mark.parametrize("sc", SCENARIOS, ids=lambda s: s["name"])
    def test_seeds_build_and_pre_emits_compile(self, sc, tmp_path):
        """Seeds must build and staged tasks must compile — broken fixtures
        would look like driver failures and poison every baseline."""
        from dojo.evals.skill_runner import _sandbox_store
        from dojo.evals.runner import compile_step
        store = _sandbox_store(tmp_path, sc.get("seed"))
        for spec in sc.get("pre_emit", []):
            compiled = compile_step(store, sc["seed"]["campaign"]["id"], dict(spec))
            assert compiled.prompt

    def test_respect_the_no_premise_debt_guard_refuses(self, tmp_path):
        """`dojo more` is the SANCTIONED door for an explicit ask, so the
        ideal agent walks it — the refusal scenario only judges fairly if
        the seed guarantees the debt guard says no. If the guard ever let
        the grant through, no_extension_session would punish correct
        behavior (owner probe 2026-07-18: the original seed carried ~3 dues
        against capacity 28 and refused only via the no-material branch)."""
        from dojo.api import DojoAPI
        from dojo.evals.skill_runner import _sandbox_store
        sc = next(s for s in SCENARIOS if s["name"] == "respect_the_no")
        store = _sandbox_store(tmp_path, sc["seed"])
        api = DojoAPI(store.engine.dojo_dir)
        res = api.more()
        assert res["extension_available"] is False
        assert "debt" in res.get("reason", ""), (
            f"the refusal must come from the DEBT GUARD, got: {res}")
        assert res["projected_due_7d"] > res["capacity_7d"]

    def test_prompt_carries_skill_message_and_persona(self):
        p = driver_prompt("teach me knots", persona="patient, hates jargon")
        assert "SKILL.md" in p and "teach me knots" in p
        assert "patient, hates jargon" in p
        assert "Never invent goals" in p
        assert "NEVER heard of `dojo`" in p, "the learner-blindness frame is load-bearing"


class TestHarnessPlumbing:
    """Free: the harness itself, proven with scripted drivers."""

    def test_scripted_driver_runs_sandboxed_and_scores(self, tmp_path):
        """A driver that creates a campaign through the real CLI must pass
        the diagnostic-mode check — and the store it writes lives under the
        harness sandbox, never the default location."""
        dojo_bin = Path(sys.executable).parent / "dojo"
        sc = {
            "name": "scripted_positive",
            "user_message": "learn knots",
            "seed": None,
            "checks": ["campaign_in_diagnostic_mode", "doctor_clean"],
        }
        driver = f'bash -c \'"{dojo_bin}" --json campaign create knots --name Knots >/dev/null 2>&1\''
        result = run_skill_scenario(sc, tmp_path, driver, timeout=120)
        assert result["score"] == 1.0, result["checks"]
        assert (tmp_path / "store" / "dojo" / "campaigns").exists(), "sandboxed store"

    def test_idle_driver_fails_checks_honestly(self, tmp_path):
        sc = {
            "name": "scripted_idle",
            "user_message": "do nothing",
            "seed": None,
            "checks": ["campaign_with_confirmed_plan"],
        }
        result = run_skill_scenario(sc, tmp_path, "bash -c 'true'", timeout=60)
        assert result["score"] == 0.0
        assert "no campaign" in result["checks"]["campaign_with_confirmed_plan"]["detail"]


@pytest.mark.eval_skill
@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda s: s["name"])
def test_skill_scenario_against_ratchet(sc, tmp_path):
    """Real driver agent (DOJO_SKILL_DRIVER, e.g. an agent CLI invocation
    that accepts the prompt as its final argument and has shell access).
    Deterministic-check scores ratchet per driver; report carries the
    transcript tail for triage."""
    driver = os.environ.get("DOJO_SKILL_DRIVER")
    assert driver, "set DOJO_SKILL_DRIVER to the driver agent command"
    result = run_skill_scenario(sc, tmp_path, driver)

    REPORTS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    (REPORTS / f"skill-{slug_for(driver)}-{stamp}-{sc['name']}.json").write_text(
        json.dumps(result, indent=1), encoding="utf-8")

    baseline_file = BASELINES / f"{slug_for(driver)}__skill.json"
    baseline = json.loads(baseline_file.read_text()) if baseline_file.exists() else {
        "driver": driver, "margin": MARGIN, "scenarios": {}}
    floor = baseline["scenarios"].get(sc["name"], {}).get("score")
    if floor is None:
        assert result["score"] > 0.0, (
            f"bootstrap refused a zero floor for {sc['name']} — "
            f"checks: { {k: v['ok'] for k, v in result['checks'].items()} }"
        )
        baseline["scenarios"][sc["name"]] = {"score": result["score"]}
        baseline_file.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    else:
        assert result["score"] >= floor - MARGIN, (
            f"{sc['name']}: {result['score']:.2f} fell below floor {floor:.2f} "
            f"(margin {MARGIN}) — a SKILL.md edit that moves scores updates "
            "the baseline in the same commit"
        )
        if result["score"] > floor:
            baseline["scenarios"][sc["name"]] = {"score": result["score"]}
            baseline_file.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
