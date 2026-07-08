"""Shared machinery for the eval suites (ADR 016).

Used by test_evals.py (Tier 2: compliance) and test_evals_quality.py (Tier 3:
judged pedagogical quality). Everything here is deterministic; the only
nondeterminism in an eval run is the models themselves.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Optional

from dojo.schemas import Attempt, Campaign, Exercise, Insight
from dojo.store import DojoStore
from dojo.tasks import compiler, service

EVALS_DIR = Path(__file__).parent.parent / "evals"


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
    for ex in seed.get("exercises", []):
        store.exercises.save(camp.id, Exercise(**ex))
    for att in seed.get("attempts", []):
        store.attempts.save(camp.id, Attempt(**{"campaign_id": camp.id, **att}))
    return store


def compile_step(store: DojoStore, campaign_id: str, spec: dict):
    """One compile spec → CompiledTask. Specs mirror the flows' compile calls."""
    camp = store.campaigns.get(campaign_id)
    args = dict(spec)
    fn = args.pop("fn")
    if fn == "generate":
        return compiler.compile_generate(store, camp, **args)
    if fn == "diagnostic":
        return compiler.compile_diagnostic(store, camp, **args)
    if fn == "reflect":
        return compiler.compile_reflect(store, camp, **args)
    if fn == "grade":
        attempt = store.attempts.get(camp.id, args.pop("attempt_id"))
        exercise = store.exercises.get(camp.id, attempt.exercise_id)
        return compiler.compile_grade(
            store, camp, exercise, attempt_id=attempt.id, user_answer=attempt.user_answer
        )
    if fn == "plan":
        return compiler.compile_plan(store, **args)
    raise ValueError(f"unknown compile fn: {fn}")


def run_command(command: str, prompt: str, timeout: int) -> str:
    proc = subprocess.run(
        shlex.split(command), input=prompt, capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"command exited {proc.returncode}: {proc.stderr[:300]}")
    return proc.stdout


def fulfill_step(store: DojoStore, compiled, fulfiller: str, timeout: int):
    """emit → fulfiller → submit: exactly the production path.
    Returns (outcome, extracted_json_text) — the extracted result is what Tier 3
    puts on trial, free of harness noise."""
    task = service.emit(store, compiled)
    raw = run_command(fulfiller, task.prompt, timeout)
    outcome = service.submit(store, task.id, raw)
    extracted: str
    try:
        extracted = json.dumps(service.extract_json(raw), indent=1)
    except ValueError:
        extracted = raw[-2000:]
    return outcome, extracted


def submit_canned(store: DojoStore, compiled, payload: dict):
    """Scripted fulfillment for chain steps whose content must be deterministic."""
    task = service.emit(store, compiled)
    outcome = service.submit(store, task.id, json.dumps(payload))
    return outcome


# ------------------------------------------------------------------
# Tier 3: rubric judging
# ------------------------------------------------------------------

_NORM = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _NORM.sub(" ", text).strip().lower()


def render_judge_prompt(scenario_context: str, output_text: str, criteria: list[dict]) -> str:
    template = (EVALS_DIR / "judge_prompt.md").read_text(encoding="utf-8")
    lines = "\n".join(f"{c['id']}: {c['question']}" for c in criteria)
    return (
        template
        .replace("{{ scenario_context }}", scenario_context)
        .replace("{{ output_text }}", output_text)
        .replace("{{ criteria_lines }}", lines)
        .strip()
    )


def judge_output(
    judge_cmd: str, scenario_context: str, output_text: str,
    criteria: list[dict], timeout: int,
) -> dict[str, Any]:
    """One judging pass. Returns {"score": weighted 0..1, "verdicts": {...},
    "discarded": [ids]} — verdicts whose evidence isn't a verbatim quote from
    the output are discarded as judge failures, never counted as passes."""
    prompt = render_judge_prompt(scenario_context, output_text, criteria)
    raw = run_command(judge_cmd, prompt, timeout)
    data = service.extract_json(raw)
    got = {v.get("id"): v for v in data.get("verdicts", []) if isinstance(v, dict)}

    total_weight, earned, discarded, verdicts = 0.0, 0.0, [], {}
    for c in criteria:
        weight = float(c.get("weight", 1.0))
        total_weight += weight
        v = got.get(c["id"])
        if not v or v.get("verdict") not in ("pass", "fail"):
            discarded.append(c["id"])
            verdicts[c["id"]] = "missing"
            continue
        if v["verdict"] == "pass":
            evidence = v.get("evidence") or ""
            if not evidence or _norm(evidence) not in _norm(output_text):
                discarded.append(c["id"])  # unproven pass = judge failure
                verdicts[c["id"]] = "discarded-unproven-pass"
                continue
            earned += weight
            verdicts[c["id"]] = "pass"
        else:
            verdicts[c["id"]] = f"fail: {v.get('why', '')}"

    score = earned / total_weight if total_weight else 0.0
    return {"score": score, "verdicts": verdicts, "discarded": discarded}


def calibration_gate(
    judge_cmd: str, scenario_context: str, references: dict,
    criteria: list[dict], timeout: int,
) -> Optional[str]:
    """The judge must score the planted good reference strictly above the
    planted bad one, blind. Returns None when calibrated, else the reason —
    callers refuse to produce scores from an uncalibrated judge (ADR 016 §T3.3)."""
    good = judge_output(judge_cmd, scenario_context, json.dumps(references["good"], indent=1),
                        criteria, timeout)
    bad = judge_output(judge_cmd, scenario_context, json.dumps(references["bad"], indent=1),
                       criteria, timeout)
    if good["score"] <= bad["score"]:
        return (
            f"judge failed calibration: good={good['score']:.2f} ≤ bad={bad['score']:.2f} "
            f"(good verdicts: {good['verdicts']}; bad verdicts: {bad['verdicts']})"
        )
    return None
