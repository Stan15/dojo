"""Output-side twin of test_token_footprint.py (owner directive 2026-07-17:
prompt work and token work are mutually non-regressing, BOTH tested).

The committed baseline (evals/baselines/output-budget.json, built by
scratch/token-diet/build_output_budget.py from measurement batteries) records
per driver, per task kind: single-shot ok-rate and median raw output bytes
per SUCCESSFUL task over the visible quality corpus — whole trace, real
compile→model→submit path.

Gate 1 (default suite, free): the baseline exists, covers every task kind
for at least one driver, and its recorded template hash matches the current
template set — so a template edit without a deliberate re-measure + baseline
update in the same commit fails loudly.

Gate 2 (opt-in, -m eval_tokens, DOJO_TOKEN_DRIVER set): re-measure and
ratchet — per kind, ok may not drop beyond the measured noise band and
median bytes/success may not rise beyond tolerance. (Driver label must
match a baseline entry: the driver is part of the measurement config —
ruling 2026-07-18.)
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from dojo.prompts import all_templates
from dojo.tasks.compiler import TEMPLATES

BASELINE = Path(__file__).parent.parent / "evals" / "baselines" / "output-budget.json"


def _template_hash() -> str:
    h = hashlib.sha256()
    for name, text in sorted(all_templates().items()):
        h.update(name.encode())
        h.update(text.encode())
    return h.hexdigest()[:16]


def _load() -> dict:
    assert BASELINE.exists(), (
        "evals/baselines/output-budget.json missing — output-byte regressions "
        "are unguarded. Rebuild: scratch/token-diet/build_output_budget.py"
    )
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def test_output_budget_covers_every_kind_for_some_driver():
    data = _load()
    kinds_covered = set()
    for d in data["drivers"].values():
        kinds_covered |= set(d["kinds"])
    missing = {k.replace("_", ".") for k in ()} or set()
    all_kinds = set(TEMPLATES)  # task kinds by contract
    uncovered = {k for k in all_kinds if k not in kinds_covered}
    assert not uncovered, f"no output-budget coverage for kinds: {sorted(uncovered)}"


def test_output_budget_tracks_current_templates():
    """A template edit MUST re-measure (or deliberately rebuild) the output
    baseline in the same commit — same discipline as token-footprint, on the
    output side."""
    data = _load()
    assert data["template_hash"] == _template_hash(), (
        "templates changed but output-budget.json was not rebuilt — run a "
        "battery (scratch/token-diet/measure.py) and "
        "scratch/token-diet/build_output_budget.py in the SAME commit"
    )


@pytest.mark.eval_tokens
def test_output_budget_ratchet():
    """Real-model re-measure vs the committed baseline. DOJO_TOKEN_DRIVER
    must equal a baseline driver label; its command is the second field,
    e.g. DOJO_TOKEN_DRIVER='api-chat/qwen3.5:4b/--no-think'."""
    import statistics as st
    import subprocess
    import sys as _sys

    label = os.environ.get("DOJO_TOKEN_DRIVER")
    assert label, "set DOJO_TOKEN_DRIVER to a baseline driver label"
    data = _load()
    assert label in data["drivers"], f"no baseline for driver {label!r}"
    repo = Path(__file__).parent.parent
    out = repo / "scratch" / "token-diet" / "baselines" / "_ratchet_run.jsonl"
    cmd = {
        "api-chat/qwen3.5:4b/--no-think":
            f"{_sys.executable} scratch/token-diet/api_driver.py qwen3.5:4b --no-think",
        "api-chat/gemma3:4b":
            f"{_sys.executable} scratch/token-diet/api_driver.py gemma3:4b",
    }[label]
    subprocess.run(
        [_sys.executable, "scratch/token-diet/measure.py", cmd, str(out), "3"],
        cwd=repo, check=True, timeout=7200,
    )
    from collections import defaultdict
    per = defaultdict(lambda: {"n": 0, "ok": 0, "bytes_ok": []})
    for line in out.read_text().splitlines():
        r = json.loads(line)
        if "kind" not in r or "error" in r:
            continue
        per[r["kind"]]["n"] += 1
        if r.get("ok"):
            per[r["kind"]]["ok"] += 1
            per[r["kind"]]["bytes_ok"].append(r["raw_bytes"])
    base = data["drivers"][label]["kinds"]
    band = data["ok_noise_band"]
    tol = data["bytes_tolerance"]
    problems = []
    for kind, b in base.items():
        m = per.get(kind)
        if m is None:
            problems.append(f"{kind}: not measured")
            continue
        if m["ok"] < b["ok"] - band:
            problems.append(f"{kind}: ok {b['ok']}→{m['ok']} beyond noise band {band}")
        if b["bytes_ok_median"] and m["bytes_ok"]:
            med = st.median(m["bytes_ok"])
            if med > b["bytes_ok_median"] * (1 + tol):
                problems.append(
                    f"{kind}: bytes/success {b['bytes_ok_median']}→{med:.0f} "
                    f"beyond +{tol:.0%}"
                )
    assert not problems, "output-budget ratchet: " + "; ".join(problems)
