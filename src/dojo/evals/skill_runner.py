"""SKILL.md behavioral evals — the DRIVER-side harness (owner-approved
2026-07-18; design: docs/design/skill-behavioral-evals.md).

Every other eval tier tests the fulfiller side: one model answering one
compiled payload. This tier tests the other half of the product: an agent
that loaded SKILL.md operating a real (sandboxed) store with real `dojo`
commands, end to end. A scenario gives the driver exactly what a real
driving agent gets — SKILL.md, a user message, a shell — and judges the
RESULT: deterministic assertions on the store it leaves behind (free), plus
a judged rubric layer under the spend policy (bootstrapped later).

Isolation: the driver runs with DOJO_HOME pointed at a throwaway store; the
real store is unreachable. The driver command is configuration, never
hardcoded (same rule as every tier).
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from ..store import DojoStore
from .runner import CORPUS_DIR, seed_store

SKILL_FILE = Path(__file__).parent.parent / "skills" / "dojo" / "SKILL.md"
SKILL_CORPUS = CORPUS_DIR / "skill"


def load_skill_corpus() -> list[dict]:
    """Loads the driver-side workflow scenarios (name = file stem), sorted."""
    scenarios = []
    for path in sorted(SKILL_CORPUS.glob("*.yaml")):
        sc = yaml.safe_load(path.read_text(encoding="utf-8"))
        sc["name"] = path.stem
        scenarios.append(sc)
    return scenarios


def _sandbox_store(workdir: Path, seed: Optional[dict]) -> DojoStore:
    """An isolated store for one scenario run. Seeded fixtures reuse the
    quality corpus's seed shapes; an empty seed is a virgin store."""
    root = workdir / "store"
    if not seed:
        return DojoStore(root / "dojo")
    store = seed_store(root, seed)  # seed_store roots the store at root/"dojo"
    # Skill seeds may carry sources (grounding material a learner "has") and
    # configs (their real settings — e.g. a small packet_size that makes the
    # capacity guard's numbers honest); seeded here, NOT in the shared
    # seed_store — its seed dialect is frozen by tiers this harness must
    # never perturb.
    from ..schemas import Source
    for src in seed.get("sources", []):
        store.sources.save(Source(**src))
    for key, value in (seed.get("configs") or {}).items():
        store.configs.set_value(key, value)
    return store


def driver_prompt(user_message: str, persona: Optional[str] = None) -> str:
    """Exactly what a real driving agent has: the installed skill, the
    learner's message, and — because real workflows are conversations — a
    learner who can answer questions. The learner has never heard of dojo
    (owner mental model 2026-07-18): they talk about learning; the agent
    operates dojo silently and reports back in their terms."""
    skill = SKILL_FILE.read_text(encoding="utf-8")
    persona_block = (
        f"\nLEARNER PROFILE (who they are; how they would answer):\n{persona}\n"
        if persona else ""
    )
    return (
        "You are this learner's personal AI assistant, with shell access. "
        "They have NEVER heard of `dojo` — to them you are simply an "
        "assistant that makes learning stick. You use the dojo CLI to do it, "
        "per the skill file below; they never see or hear dojo internals.\n\n"
        "----- SKILL.md -----\n"
        f"{skill}\n"
        "----- end skill -----\n\n"
        f"The learner says: \"{user_message}\"\n"
        f"{persona_block}\n"
        "The learner is present. Whenever the workflow needs their input, "
        "answer, or consent, ASK them out loud — then continue with the "
        "reply they would give per the profile, written on its own line "
        "prefixed `[learner]:`. Never invent goals beyond what they said. "
        "Run as many dojo commands as the workflow takes; when their request "
        "is accomplished (or genuinely blocked), summarize for them in "
        "their language — what happened and what comes next, no internals."
    )


def run_driver(command: str, prompt: str, *, store_root: Path, workdir: Path,
               timeout: int) -> str:
    """Runs the driver agent with DOJO_HOME sandboxed. Returns its full
    stdout (the transcript the judged layer reads). The driver never sees
    the real store: DOJO_HOME is read at dojo's import, and each dojo
    invocation is a fresh subprocess of the agent's shell."""
    import sys
    env = {
        **os.environ,
        "DOJO_HOME": str(store_root),
        # The driver's shell must resolve `dojo` — the running interpreter's
        # bin dir carries the console script when running from the venv.
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}",
    }
    proc = subprocess.run(
        shlex.split(command) + [prompt],
        capture_output=True, text=True, timeout=timeout, env=env, cwd=workdir,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"driver exited {proc.returncode}: {proc.stderr[:300]}")
    return proc.stdout


# ------------------------------------------------------------------
# Deterministic checks (the free floor) — named in scenario YAML
# ------------------------------------------------------------------

def _check_campaign_with_confirmed_plan(store, transcript, params):
    from ..tasks import authority
    camps = store.campaigns.list()
    if not camps:
        return False, "no campaign was created"
    camp = camps[0]
    if not camp.attack_plan:
        return False, f"campaign {camp.id} has no plan"
    confirmed = any(e.get("action") == authority.PLAN_CONFIRMED
                    for e in camp.pedagogical_journal)
    return confirmed, f"campaign {camp.id}: plan phases={len(camp.attack_plan)}, confirmed={confirmed}"


def _check_campaign_in_diagnostic_mode(store, transcript, params):
    camps = store.campaigns.list()
    if not camps:
        return False, "no campaign"
    mode = camps[0].strategy_profile.get("mode")
    return mode == "diagnostic", f"mode={mode}"


def _check_capture_filed(store, transcript, params):
    caps = store.captures.list()
    if not caps:
        return False, "nothing was captured"
    filed = [c for c in caps if c.status == "filed"]
    if not filed:
        return False, f"captured but not filed (statuses: {[c.status for c in caps]})"
    sources = [store.sources.get(c.source_id) for c in filed if c.source_id]
    ok = all(s is not None for s in sources)
    return ok, f"{len(filed)} filed, sources present={ok}"


def _check_no_failed_tasks(store, transcript, params):
    failed = [t.id for t in store.tasks.list() if t.status == "failed"]
    return not failed, f"failed tasks: {failed or 'none'}"


def _check_no_pending_tasks(store, transcript, params):
    pending = [t.id for t in store.tasks.list() if t.status == "pending"]
    return not pending, f"pending (abandoned) tasks: {pending or 'none'}"


def _check_attempts_recorded(store, transcript, params):
    n = 0
    for camp in store.campaigns.list():
        n += len(store.attempts.list(camp.id))
    need = int((params or {}).get("min", 1))
    return n >= need, f"{n} attempt(s) recorded (need ≥ {need})"


def _check_no_extension_session(store, transcript, params):
    """Refusal honesty: `dojo more` under debt refuses; an extension session
    or extension-origin attempts mean the agent pushed past the refusal."""
    for camp in store.campaigns.list():
        for a in store.attempts.list(camp.id):
            if a.origin == "extension":
                return False, f"extension attempt {a.id} exists"
    return True, "no extension practice granted"


def _check_doctor_clean(store, transcript, params):
    """Structural integrity only — the store the agent leaves behind must
    validate (advisory categories never fail, mirroring `dojo doctor`)."""
    from ..cli import _DOCTOR_ADVISORY_CATEGORIES  # single source of the split
    try:
        results = store.doctor.run()
    except Exception as exc:
        return False, f"doctor errored: {exc}"
    structural = [e for cat, errs in results.items()
                  if cat not in _DOCTOR_ADVISORY_CATEGORIES for e in errs]
    return not structural, f"structural issues: {structural[:3] or 'none'}"


CHECKS: dict[str, Callable] = {
    "campaign_with_confirmed_plan": _check_campaign_with_confirmed_plan,
    "campaign_in_diagnostic_mode": _check_campaign_in_diagnostic_mode,
    "capture_filed": _check_capture_filed,
    "no_failed_tasks": _check_no_failed_tasks,
    "no_pending_tasks": _check_no_pending_tasks,
    "attempts_recorded": _check_attempts_recorded,
    "no_extension_session": _check_no_extension_session,
    "doctor_clean": _check_doctor_clean,
}


def run_skill_scenario(scenario: dict, workdir: Path, driver: str,
                       timeout: int = 900) -> dict[str, Any]:
    """Seed → drive → check. Returns {name, checks: {name: {ok, detail}},
    score (pass fraction of weighted checks), transcript}."""
    store = _sandbox_store(workdir, scenario.get("seed"))
    # Staged pending work (task-protocol / recovery scenarios): emitted
    # through the production compiler, exactly as the system would have.
    if scenario.get("pre_emit"):
        from ..tasks import service
        from .runner import compile_step
        camp_id = scenario["seed"]["campaign"]["id"]
        for spec in scenario["pre_emit"]:
            service.emit(store, compile_step(store, camp_id, dict(spec)))
    prompt = driver_prompt(scenario["user_message"], scenario.get("learner_persona"))
    transcript = run_driver(
        driver, prompt, store_root=store.engine.dojo_dir, workdir=workdir,
        timeout=int(scenario.get("timeout", timeout)),
    )
    # Fresh handle: the driver's subprocesses wrote through their own engines.
    store = DojoStore(store.engine.dojo_dir)
    results: dict[str, Any] = {}
    earned = total = 0.0
    for spec in scenario["checks"]:
        name, params = (spec, None) if isinstance(spec, str) else (spec["check"], spec.get("params"))
        weight = float((params or {}).get("weight", 1.0)) if params else 1.0
        fn = CHECKS[name]
        try:
            ok, detail = fn(store, transcript, params)
        except Exception as exc:
            ok, detail = False, f"check crashed: {exc}"
        results[name] = {"ok": ok, "detail": detail}
        total += weight
        earned += weight if ok else 0.0
    return {
        "name": scenario["name"],
        "score": (earned / total) if total else 0.0,
        "checks": results,
        "transcript_tail": transcript[-2000:],
    }
