"""Splice iterW2 plan mini-battery rows into the iterW full battery.

Per WORKBENCH NEXT step 4: read iterW_<model>.jsonl, drop rows with
kind=="campaign.plan", append all rows from iterW2_<model>_plan.jsonl,
write iterW2_<model>.jsonl combined.

Usage: python scratch/prompt-lab/splice_iterw2.py <model_slug>
  e.g. gemma3_4b | qwen35_4b
"""
import json
import sys
from pathlib import Path

BASE = Path("scratch/token-diet/baselines")


def main() -> int:
    slug = sys.argv[1]
    full = [json.loads(l) for l in (BASE / f"iterW_{slug}.jsonl").read_text().splitlines() if l.strip()]
    mini = [json.loads(l) for l in (BASE / f"iterW2_{slug}_plan.jsonl").read_text().splitlines() if l.strip()]
    kept = [r for r in full if r.get("kind") != "campaign.plan"]
    dropped = len(full) - len(kept)
    bad = [r for r in mini if r.get("kind") != "campaign.plan"]
    if bad:
        raise SystemExit(f"mini file has non-plan rows: {[(r['scenario'], r.get('kind')) for r in bad]}")
    infra = [r for r in mini if "error" in r]
    if infra:
        raise SystemExit(f"mini file has infra-error rows — battery invalid, refuse splice: {[r['scenario'] for r in infra]}")
    combined = kept + mini
    out = BASE / f"iterW2_{slug}.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in combined) + "\n", encoding="utf-8")
    ok = sum(1 for r in combined if r.get("ok"))
    print(f"{out.name}: {len(full)} full rows - {dropped} plan + {len(mini)} mini = {len(combined)} rows; ok={ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
