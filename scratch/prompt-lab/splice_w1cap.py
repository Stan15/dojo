"""Splice W1 (word-cap tolerance) mini-battery rows over the iterQ full
batteries to produce the merged jsonls the output-budget rebuild reads.

Rule: for any scenario the W1 batteries re-drove, ALL its rows come from the
W1 run (the whole scenario was re-driven under the W1 arm); every other
scenario keeps its iterQ rows. Usage:

    python scratch/prompt-lab/splice_w1cap.py qwen35_4b
    python scratch/prompt-lab/splice_w1cap.py gemma3_4b
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path("scratch/token-diet/baselines")


def rows(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def main() -> int:
    slug = sys.argv[1]
    full = rows(BASE / f"iterQ_{slug}.jsonl")
    w1: list[dict] = []
    for part in ("plan", "reflect"):
        p = BASE / f"iterW1cap_{slug}_{part}.jsonl"
        if p.exists():
            w1.extend(rows(p))
    redriven = {r["scenario"] for r in w1}
    merged = [r for r in full if r["scenario"] not in redriven] + w1
    out = BASE / f"w1cap_{slug}_full.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n",
                   encoding="utf-8")
    ok = sum(1 for r in merged if r.get("ok"))
    print(f"wrote {out}: {len(merged)} rows, {ok} ok ({len(w1)} W1 rows over "
          f"{len(full)} iterQ rows, {len(redriven)} scenarios re-driven)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
