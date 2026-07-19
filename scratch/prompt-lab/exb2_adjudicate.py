"""EXB2 corrected-scope adjudication: path-segmented bleed. For each reflect
row, recompiles the scenario's reflect payload to determine which ops
fragment it received, then counts create-example bleed ONLY on the
with-insights (suppressed) path. Also reports ok-rate and create-fails.

    python scratch/prompt-lab/exb2_adjudicate.py <battery.jsonl>
"""
import json
import re
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, "src")
from dojo.evals.runner import CORPUS_DIR, compile_step, seed_store  # noqa: E402

battery = Path(sys.argv[1])
rows = [json.loads(l) for l in battery.read_text().splitlines() if l.strip()]

path_cache = {}
def suppressed_path(scenario: str) -> bool:
    """True if this scenario's reflect payload took the with-insights
    (create-suppressed) fragment."""
    if scenario not in path_cache:
        sc = yaml.safe_load((CORPUS_DIR / "quality" / f"{scenario}.yaml").read_text())
        with tempfile.TemporaryDirectory() as td:
            store = seed_store(Path(td), sc["seed"])
            cid = sc["seed"]["campaign"]["id"]
            for step in sc["steps"]:
                if step.get("compile", {}).get("fn") == "reflect":
                    p = compile_step(store, cid, step["compile"]).prompt
                    path_cache[scenario] = '"op": "create"' not in p
                    break
            else:
                path_cache[scenario] = None
    return path_cache[scenario]

ok = sum(1 for r in rows if r.get("ok"))
create_fails = sum(1 for r in rows if any("op=create requires" in str(e) for e in r.get("errors", [])))
supp_create_bleed, supp_update_bleed, noins_bleed = [], [], []
for r in rows:
    if r.get("kind") != "campaign.reflect":
        continue
    raw = r.get("raw", "").lower()
    create_hit = "nib" in raw or "ink_loading" in raw
    update_hit = "letterform" in raw or "crowds" in raw
    if not (create_hit or update_hit):
        continue
    if suppressed_path(r["scenario"]):
        if create_hit:
            supp_create_bleed.append(r["scenario"])
        if update_hit:
            supp_update_bleed.append(r["scenario"])
    else:
        noins_bleed.append(r["scenario"])

print(f"{battery.name}: ok {ok}/{len(rows)}; create-fails {create_fails}")
print(f"  with-insights path: CREATE-bleed {len(supp_create_bleed)} (rule: 0) "
      f"{supp_create_bleed}; update-bleed {len(supp_update_bleed)}")
print(f"  no-insights path (out of arm scope): bleed {len(noins_bleed)}")
