"""EX-BLEED adjudication: for each battery, count (a) OLD example-value
bleed (must go to ~0 — the values are gone from templates), (b) NEW
calligraphy-value bleed (the real test: do orthogonal examples still get
copied?), (c) ok-rate vs the recorded baseline.

    python scratch/prompt-lab/exb_adjudicate.py
"""
import json
from pathlib import Path

OLD = ["rushes multi-step problems", "submits without re-reading the prompt",
       "process.skips_checking"]
NEW = ["crowds letterforms near margins", "overloads the nib before flourishes",
       "calligraphy.ink_loading", "letterform", "calligraphy", "nib"]

BASE = {"iterEXB_gemma3_4b_reflect.jsonl": ("gemma", 27, 30, 16),
        "iterEXB_qwen35_4b_reflect.jsonl": ("qwen", 16, 30, 9)}

for name, (label, base_ok, base_n, base_bleed) in BASE.items():
    p = Path("scratch/token-diet/baselines") / name
    if not p.exists():
        print(f"{label}: no file yet")
        continue
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    refl = [r for r in rows if r.get("kind") == "campaign.reflect"]
    ok = sum(1 for r in rows if r.get("ok"))
    old_hits = sum(1 for r in refl if any(o in r.get("raw", "").lower() for o in [x.lower() for x in OLD]))
    new_hits = [r["scenario"] for r in refl if any(nv in r.get("raw", "").lower() for nv in [x.lower() for x in NEW])]
    print(f"{label}: ok {ok}/{len(rows)} (baseline {base_ok}/{base_n}); "
          f"OLD-value bleed {old_hits}/{len(refl)} (was {base_bleed}); "
          f"NEW-value bleed {len(new_hits)}/{len(refl)}")
    for s in new_hits[:8]:
        print(f"   new-bleed: {s}")
