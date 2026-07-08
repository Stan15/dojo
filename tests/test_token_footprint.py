"""Token-footprint regression (owner directive 2026-07-07): every byte a prompt
or the skill grows is money spent in EVERY future conversation, so growth must
be a deliberate, reviewed diff — never drift.

The committed baseline (evals/baselines/token-footprint.json) records the
compiled payload size per task kind on fixed fixtures, plus SKILL.md. The test
fails when any measurement drifts beyond tolerance in EITHER direction — a
shrink you didn't intend is a lost section, not a win. Changing the footprint
on purpose = update the baseline file in the same commit and let review see it.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dojo.evals.runner import compile_step, load_corpus, seed_store

BASELINE = Path(__file__).parent.parent / "evals" / "baselines" / "token-footprint.json"
SKILL = Path(__file__).parent.parent / "skills" / "dojo" / "SKILL.md"
TOLERANCE = 0.05  # ±5%: whitespace-level churn passes; a new section does not


@pytest.fixture(autouse=True)
def no_git():
    with patch("dojo.store.engine.init_git"), patch("dojo.store.engine.commit_git"):
        yield


def measure(tmp_path: Path) -> dict[str, int]:
    """Compiled payload bytes per task kind, on the corpus's own fixed
    scenarios (first scenario of each compile fn encountered)."""
    sizes: dict[str, int] = {}
    for i, sc in enumerate(load_corpus("quality") + load_corpus("compliance")):
        for step in sc["steps"] if "steps" in sc else [{"compile": sc["compile"]}]:
            fn = step["compile"]["fn"]
            if fn in sizes:
                continue
            store = seed_store(tmp_path / f"m{i}_{fn}", sc["seed"])
            compiled = compile_step(store, sc["seed"]["campaign"]["id"], step["compile"])
            sizes[fn] = compiled.payload_bytes
    sizes["skill_md"] = len(SKILL.read_bytes())
    return dict(sorted(sizes.items()))


def test_token_footprint_matches_committed_baseline(tmp_path: Path):
    measured = measure(tmp_path)
    if not BASELINE.exists():  # bootstrap: write once, review, commit
        BASELINE.write_text(json.dumps({
            "note": "compiled payload bytes per task kind + skill; ~4 bytes ≈ 1 token",
            "tolerance": TOLERANCE,
            "bytes": measured,
        }, indent=2), encoding="utf-8")
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["bytes"]

    drifted = {}
    for key, size in measured.items():
        old = baseline.get(key)
        if old is None or abs(size - old) / old > TOLERANCE:
            drifted[key] = {"baseline": old, "now": size,
                            "delta_pct": None if not old else round(100 * (size - old) / old, 1)}
    assert not drifted, (
        f"token footprint drifted beyond ±{TOLERANCE:.0%}: {drifted}. "
        "If intentional, update evals/baselines/token-footprint.json in the same "
        "commit — footprint changes must be visible in review, never drift."
    )
    stale = set(baseline) - set(measured)
    assert not stale, f"baseline entries no longer measured (update the file): {stale}"
