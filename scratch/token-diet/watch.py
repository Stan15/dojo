"""Live campaign scoreboard: every battery file, plus campaign totals.
Usage: while true; do clear; .venv/bin/python scratch/token-diet/watch.py; sleep 15; done
"""
import glob
import json
import time

N = 64  # scenarios per full battery (one driven step each)
# Campaign plan: batteries expected per phase (denominator for the total line).
PLAN = {"base": 5, "armJ": 5, "base2": 2, "armJS": 5}

print(time.strftime("%H:%M:%S"), "— scenarios per battery:", N)
done_runs = 0
for path in sorted(glob.glob("scratch/token-diet/baselines/*.jsonl")):
    name = path.split("/")[-1]
    rows = [json.loads(l) for l in open(path) if l.strip()]
    scen = {r["scenario"] for r in rows}
    driven = [r for r in rows if "kind" in r and "error" not in r]
    ok = [r for r in driven if r.get("ok")]
    infra = [r for r in rows if "error" in r]
    state = "DNF " if "DNF" in name else ("done" if len(scen) >= N else "RUN ")
    if "DNF" not in name:
        done_runs += len(scen)
    print(f"  {state} {name:<34} scen:{len(scen):>3}/{N}  ok:{len(ok):>3}"
          f"  rej:{len(driven)-len(ok):>3}  infra:{len(infra):>2}")
total = sum(PLAN.values()) * N
print(f"\ncampaign scenario-runs: {done_runs}/{total} ({100*done_runs/total:.0f}%)"
      f"  [plan: {' + '.join(f'{k}×{v}' for k, v in PLAN.items())} batteries]"
      "\n  (judged spot-set, winner gate, SKILL trim follow the batteries)")
