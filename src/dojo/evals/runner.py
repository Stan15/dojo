"""Benchmark execution: seed → compile → drive → submit → (judge) → aggregate.

Everything here is deterministic; the only nondeterminism in a run is the
models themselves. Scoring reuses the production validators/appliers — a
benchmark pass means the real system would have accepted the same output.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from ..schemas import Attempt, Campaign, Exercise, Insight
from ..store import DojoStore
from ..tasks import compiler, service

PACKAGE_DIR = Path(__file__).parent
CORPUS_DIR = PACKAGE_DIR / "corpus"

CATEGORY_BLURBS = {
    "contract-compliance": "produces valid, applyable output at all",
    "personalization": "uses the learner's profile, errors, and preferences",
    "calibration": "adjusts difficulty/scaffolding from evidence, without churn",
    "planning": "plans lean, deadline- and vagueness-aware campaigns",
    "grading-integrity": "grades content, immune to confident nonsense",
    "meta-learning": "knows when to ask instead of generate",
    "domain-breadth": "handles widely varying subject types well",
}


def slug_for(command: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", command.lower()).strip("-")[:40]


def load_corpus(tier: str) -> list[dict]:
    """tier: "compliance" | "quality". Scenarios sorted by name; each carries
    its path stem as `name` and a `category`."""
    scenarios = []
    for path in sorted((CORPUS_DIR / tier).glob("*.yaml")):
        sc = yaml.safe_load(path.read_text(encoding="utf-8"))
        sc["name"] = path.stem
        sc.setdefault("category", "contract-compliance")
        scenarios.append(sc)
    return scenarios


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
    Returns (outcome, extracted_json_text, byte_counts)."""
    task = service.emit(store, compiled)
    raw = run_command(fulfiller, task.prompt, timeout)
    outcome = service.submit(store, task.id, raw)
    try:
        extracted = json.dumps(service.extract_json(raw), indent=1)
    except ValueError:
        extracted = raw[-2000:]
    counts = {
        "prompt_bytes": task.payload_bytes,
        "response_bytes": len(extracted.encode("utf-8")),
    }
    return outcome, extracted, counts


def submit_canned(store: DojoStore, compiled, payload: dict):
    task = service.emit(store, compiled)
    return service.submit(store, task.id, json.dumps(payload))


# ------------------------------------------------------------------
# Tier 3 judging
# ------------------------------------------------------------------

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


def _evidence_core(quote: str) -> str:
    """Judges often wrap quotes in ellipses or quotation marks; the core must
    still be verbatim."""
    return _norm(quote).strip("…. \"'“”‘’")


def render_judge_prompt(scenario_context: str, output_text: str, criteria: list[dict]) -> str:
    template = (PACKAGE_DIR / "judge_prompt.md").read_text(encoding="utf-8")
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
    """One judging pass → {"score", "verdicts", "discarded"}. Passes without a
    verbatim quote from the judged output are discarded as judge failures."""
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
            if not evidence or _evidence_core(evidence) not in _norm(output_text):
                discarded.append(c["id"])
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
    """Judge must rank the planted good reference strictly above the bad one,
    blind. Returns None when calibrated, else the reason."""
    good = judge_output(judge_cmd, scenario_context,
                        json.dumps(references["good"], indent=1), criteria, timeout)
    bad = judge_output(judge_cmd, scenario_context,
                       json.dumps(references["bad"], indent=1), criteria, timeout)
    if good["score"] <= bad["score"]:
        return (
            f"judge failed calibration: good={good['score']:.2f} ≤ bad={bad['score']:.2f}"
        )
    return None


# ------------------------------------------------------------------
# Orchestration shared by `dojo benchmark` and the dev eval suites
# ------------------------------------------------------------------

@dataclass
class ScenarioResult:
    name: str
    category: str
    tier: str  # compliance | quality
    score: float  # compliance: 0/1; quality: weighted pass fraction
    detail: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None  # infrastructure/judge failure, not model quality


def execute_quality_scenario(scenario: dict, tmp_path: Path, driver: str, timeout: int) -> str:
    """Runs steps; returns the final step's extracted output (the thing on
    trial). Scripted steps isolate the judged step from upstream variance."""
    store = seed_store(tmp_path, scenario["seed"])
    campaign_id = scenario["seed"]["campaign"]["id"]
    final_output = None
    for step in scenario["steps"]:
        compiled = compile_step(store, campaign_id, step["compile"])
        if "respond_with" in step:
            outcome = submit_canned(store, compiled, step["respond_with"])
            if not outcome.ok:
                raise RuntimeError(f"scripted step rejected: {outcome.errors}")
            final_output = json.dumps(step["respond_with"], indent=1)
        else:
            outcome, extracted, counts = fulfill_step(store, compiled, driver, timeout)
            if not outcome.ok:
                raise ComplianceFailure(outcome.errors)
            final_output = extracted
            byte_log.append(counts)
    assert final_output is not None
    return final_output


class ComplianceFailure(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors[:3]))
        self.errors = errors


def run_benchmark(
    *,
    driver: str,
    judge: Optional[str],
    workdir: Path,
    timeout: int = 300,
    tiers: tuple[str, ...] = ("compliance", "quality"),
    progress: Callable[[str], None] = lambda msg: None,
) -> dict[str, Any]:
    """Runs the shipped corpus against a driver (and judge, for quality).
    Returns a report dict; rendering is the caller's job."""
    judge = judge or driver
    results: list[ScenarioResult] = []
    byte_counts: list[dict[str, int]] = []

    if "compliance" in tiers:
        for sc in load_corpus("compliance"):
            progress(f"compliance · {sc['name']}")
            try:
                store = seed_store(workdir / f"c_{sc['name']}", sc["seed"])
                compiled = compile_step(store, sc["seed"]["campaign"]["id"], sc["compile"])
                outcome, _, counts = fulfill_step(store, compiled, driver, timeout)
                byte_counts.append(counts)
                results.append(ScenarioResult(
                    name=sc["name"], category=sc["category"], tier="compliance",
                    score=1.0 if outcome.ok else 0.0,
                    detail={} if outcome.ok else {"errors": outcome.errors[:3]},
                ))
            except Exception as e:
                results.append(ScenarioResult(
                    name=sc["name"], category=sc["category"], tier="compliance",
                    score=0.0, error=str(e)[:200],
                ))

    if "quality" in tiers:
        for sc in load_corpus("quality"):
            progress(f"quality · {sc['name']}")
            context = sc["scenario_context"].strip()
            criteria = sc["judge_rubric"]
            try:
                problem = calibration_gate(judge, context, sc["references"], criteria, timeout)
                if problem:
                    results.append(ScenarioResult(
                        name=sc["name"], category=sc["category"], tier="quality",
                        score=0.0, error=problem,
                    ))
                    continue
                output_text = execute_quality_scenario(
                    sc, workdir / f"q_{sc['name']}", driver, timeout, byte_log=byte_counts,
                )
                judged = judge_output(judge, context, output_text, criteria, timeout)
                results.append(ScenarioResult(
                    name=sc["name"], category=sc["category"], tier="quality",
                    score=judged["score"],
                    detail={"verdicts": judged["verdicts"], "discarded": judged["discarded"]},
                ))
            except ComplianceFailure as e:
                results.append(ScenarioResult(
                    name=sc["name"], category=sc["category"], tier="quality",
                    score=0.0, detail={"errors": e.errors[:3]},
                    error="driver output rejected by the contract (compliance failure)",
                ))
            except Exception as e:
                results.append(ScenarioResult(
                    name=sc["name"], category=sc["category"], tier="quality",
                    score=0.0, error=str(e)[:200],
                ))

    return summarize(driver, judge, results, byte_counts)


def summarize(
    driver: str, judge: str, results: list[ScenarioResult],
    byte_counts: Optional[list[dict[str, int]]] = None,
) -> dict[str, Any]:
    categories: dict[str, dict[str, Any]] = {}
    for r in results:
        cat = categories.setdefault(r.category, {"scores": [], "scenarios": []})
        cat["scores"].append(r.score)
        cat["scenarios"].append({
            "name": r.name, "tier": r.tier, "score": r.score,
            "detail": r.detail, "error": r.error,
        })
    for name, cat in categories.items():
        cat["mean"] = sum(cat["scores"]) / len(cat["scores"])
        cat["blurb"] = CATEGORY_BLURBS.get(name, "")
        del cat["scores"]
    scored = [r for r in results if r.error is None]
    footprint = None
    if byte_counts:
        n = len(byte_counts)
        mean_in = sum(c["prompt_bytes"] for c in byte_counts) / n
        mean_out = sum(c["response_bytes"] for c in byte_counts) / n
        footprint = {
            "driver_calls_measured": n,
            "mean_prompt_bytes": round(mean_in),
            "mean_response_bytes": round(mean_out),
            "approx_prompt_tokens": round(mean_in / 4),
            "approx_response_tokens": round(mean_out / 4),
        }
    return {
        "token_footprint": footprint,
        "driver": driver,
        "judge": judge,
        "pair": f"{slug_for(driver)}__{slug_for(judge)}",
        "categories": dict(sorted(categories.items(), key=lambda kv: -kv[1]["mean"])),
        "overall": (sum(r.score for r in scored) / len(scored)) if scored else 0.0,
        "errors": sum(1 for r in results if r.error),
        "total_scenarios": len(results),
    }
