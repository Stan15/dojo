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
COMPILE_FN_TO_KIND = {
    "generate": "exercise.generate",
    "diagnostic": "exercise.diagnostic",
    "grade": "attempt.grade",
    "reflect": "campaign.reflect",
    "plan": "campaign.plan",
}


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", QUALITY_SCENARIOS, ids=lambda p: p.stem)
class TestCorpusIntegrity:
    def test_shape(self, path: Path):
        sc = load(path)
        for key in ("category", "scenario_context", "seed", "steps", "judge_rubric", "references"):
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
