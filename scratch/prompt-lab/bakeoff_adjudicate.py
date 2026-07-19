"""Score bake-off batteries: per-model ok-rates, per-kind breakdown, and the
best-in-class table. Run any time; scores whatever bakeoff_*.jsonl exist.

    python scratch/prompt-lab/bakeoff_adjudicate.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

B = Path("scratch/token-diet/baselines")
FOOTPRINT_GB = {  # ollama list sizes, recorded 2026-07-19
    "qwen35_08b_w1": 1.0, "gemma3_1b_w1": 0.8, "lfm25_12b_w1": 0.73,
    "lfm25think_12b_w1": 0.73, "granite4_1b_w1": 3.3, "qwen35_2b_w1": 2.7,
}

rows_by_model: dict[str, list[dict]] = {}
for p in sorted(B.glob("bakeoff_*.jsonl")):
    slug = p.stem.removeprefix("bakeoff_")
    rows_by_model[slug] = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]

print(f"{'model':22} {'GB':>4} {'rows-ok':>9} {'ok%':>5}  per-kind")
for slug, rows in sorted(rows_by_model.items(), key=lambda kv: -(
        sum(1 for r in kv[1] if r.get("ok")) / max(1, sum(1 for r in kv[1] if "error" not in r)))):
    driven = [r for r in rows if "error" not in r]
    ok = sum(1 for r in driven if r.get("ok"))
    per = defaultdict(lambda: [0, 0])
    for r in driven:
        per[r.get("kind", "?")][1] += 1
        if r.get("ok"):
            per[r.get("kind", "?")][0] += 1
    kinds = " ".join(f"{k.split('.')[-1]}={a}/{n}" for k, (a, n) in sorted(per.items()))
    infra = len(rows) - len(driven)
    print(f"{slug:22} {FOOTPRINT_GB.get(slug, 0):>4} {ok:>4}/{len(driven):<4} "
          f"{100*ok/max(1,len(driven)):>4.0f}%  {kinds}"
          + (f"  [{infra} infra]" if infra else ""))
