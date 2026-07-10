"""Deterministic integrity checks for the Tier-3 quality corpus — run in normal
CI (no models). The corpus is product surface: a scenario with a broken seed,
an invalid reference, or a rubric that can't be judged would silently corrupt
every future baseline. This file makes corpus rot impossible.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from dojo.evals.runner import CORPUS_DIR, compile_step, seed_store, submit_canned
from dojo.schemas import RESULT_SCHEMAS
from dojo.tasks import service

QUALITY_SCENARIOS = sorted((CORPUS_DIR / "quality").glob("*.yaml"))
# Holdout scenarios get the same MECHANICAL integrity checks (shape, schema,
# executability) — that is their entire automated QA, since nobody who tunes
# prompts may read them (see tests/test_evals_holdout.py). They are excluded
# from the coverage floors: holdout size is a protocol matter, not a ratchet.
HOLDOUT_SCENARIOS = sorted((CORPUS_DIR / "holdout").glob("*.yaml"))
COMPILE_FN_TO_KIND = {
    "generate": "exercise.generate",
    "diagnostic": "exercise.diagnostic",
    "grade": "attempt.grade",
    "reflect": "campaign.reflect",
    "plan": "campaign.plan",
    "route": "capture.route",
    "goal_route": "goal.route",
}


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class TestCorpusCoverage:
    """The corpus must be SERIOUS and VARIED (owner directive 2026-07-07) —
    breadth is a ratcheted invariant, not an aspiration. These floors may only
    ever go UP; raising them is how the corpus grows deliberately."""

    MIN_TOTAL = 41
    MIN_PER_CATEGORY = {
        "personalization": 3,
        "calibration": 6,
        "planning": 6,
        "grading-integrity": 4,
        "meta-learning": 3,
        "domain-breadth": 4,
        "change-authority": 2,
        "routing": 4,
        "robustness": 7,
    }
    MIN_DISTINCT_DOMAINS = 14

    def _scenarios(self) -> list[dict]:
        return [load(p) for p in QUALITY_SCENARIOS]

    def test_total_floor(self):
        assert len(QUALITY_SCENARIOS) >= self.MIN_TOTAL

    def test_every_category_meets_its_floor(self):
        counts: dict[str, int] = {}
        for sc in self._scenarios():
            counts[sc["category"]] = counts.get(sc["category"], 0) + 1
        for category, floor in self.MIN_PER_CATEGORY.items():
            assert counts.get(category, 0) >= floor, (
                f"{category}: {counts.get(category, 0)} scenarios < floor {floor}"
            )
        unknown = set(counts) - set(self.MIN_PER_CATEGORY)
        assert not unknown, f"new categories need a floor here too: {unknown}"

    def test_domain_variety_floor(self):
        domains = {sc["domain"] for sc in self._scenarios()}
        assert len(domains) >= self.MIN_DISTINCT_DOMAINS, (
            f"only {len(domains)} distinct domains: {sorted(domains)}"
        )

    def test_signal_variety(self):
        """The corpus must test the LEARNING LOOP, not just single-shot output:
        at least one longitudinal chain, one intervention-expected scenario, one
        false-intervention control, and one plan-elucidation scenario."""
        scenarios = self._scenarios()
        assert any(len(sc["steps"]) > 1 for sc in scenarios), "no longitudinal chain"
        assert any(
            sc["references"]["good"].get("intervention") for sc in scenarios
        ), "no intervention-expected scenario"
        assert any(
            sc["references"]["bad"].get("intervention") for sc in scenarios
        ), "no false-intervention control"
        assert any(
            sc["references"]["good"].get("refinement_questions") for sc in scenarios
        ), "no plan-elucidation scenario"


@pytest.mark.parametrize("path", QUALITY_SCENARIOS + HOLDOUT_SCENARIOS, ids=lambda p: p.stem)
class TestCorpusIntegrity:
    def test_shape(self, path: Path):
        sc = load(path)
        for key in ("category", "domain", "scenario_context", "seed", "steps", "judge_rubric", "references"):
            assert key in sc, f"missing {key}"
        ids = [c["id"] for c in sc["judge_rubric"]]
        assert len(ids) == len(set(ids)), "duplicate rubric criterion ids"
        assert all(c["question"].strip().endswith("?") for c in sc["judge_rubric"])
        assert {"good", "bad"} <= sc["references"].keys()

    def test_references_validate_against_final_step_schema(self, path: Path):
        """Both planted references must be schema-valid: the calibration gate
        judges pedagogy, and schema-invalid references would test compliance
        instead."""
        sc = load(path)
        kind = COMPILE_FN_TO_KIND[sc["steps"][-1]["compile"]["fn"]]
        schema = RESULT_SCHEMAS[kind]
        for name in ("good", "bad"):
            schema.model_validate(sc["references"][name])

    def test_scenario_executes_with_canned_final_response(self, path: Path, tmp_path: Path):
        """Seeds must build, every step must compile, scripted steps must apply,
        and the GOOD reference must be accepted by the real submit path when
        played as the final step's answer — proving driver compliance is
        achievable and the judged output corresponds to applyable state."""
        sc = load(path)
        store = seed_store(tmp_path, sc["seed"])
        campaign_id = sc["seed"]["campaign"]["id"]
        for step in sc["steps"][:-1]:
            compiled = compile_step(store, campaign_id, step["compile"])
            assert "respond_with" in step, "non-final steps must be scripted"
            outcome = submit_canned(store, compiled, step["respond_with"])
            assert outcome.ok, f"scripted step rejected: {outcome.errors}"

        final = sc["steps"][-1]
        compiled = compile_step(store, campaign_id, final["compile"])
        payload = final.get("respond_with") or sc["references"]["good"]
        task = service.emit(store, compiled)
        outcome = service.submit(store, task.id, json.dumps(payload))
        assert outcome.ok, (
            f"the GOOD reference was rejected by the production submit path: {outcome.errors}"
        )


def test_judged_output_renders_human_readable_unicode():
    """The judge quotes what it READS; ensure_ascii escaping made honest French
    quotes fail the verbatim check and silently sank accent-heavy scenarios
    (insight_targeting calibration failed three runs straight)."""
    import json as _json
    from dojo.evals.runner import _norm

    reference = {"prompt": "Traduisez : Elle serait venue à la fête."}
    rendered = _json.dumps(reference, indent=1, ensure_ascii=False)
    assert "à la fête" in rendered, "judged output must contain readable unicode"
    assert _norm("elle serait venue à la fête") in _norm(rendered)
