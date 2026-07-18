"""Build evals/baselines/output-budget.json from measurement battery jsonls.

Usage: python scratch/token-diet/build_output_budget.py \
           "<driver-label>=<battery.jsonl>" [more pairs...]

Records, per driver label, per task kind: driven steps, single-shot ok count,
and median raw output bytes per SUCCESSFUL task (whole trace) — plus a hash
of the current template set. tests/test_output_budget.py gates coherence
(template change without a deliberate baseline update fails the default
suite) and ratchets against re-measures under -m eval_tokens.
"""
from __future__ import annotations

import hashlib
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

from dojo.prompts import all_templates

OUT = Path("evals/baselines/output-budget.json")


def template_hash() -> str:
    h = hashlib.sha256()
    for name, text in sorted(all_templates().items()):
        h.update(name.encode())
        h.update(text.encode())
    return h.hexdigest()[:16]


def summarize(path: str) -> dict:
    per = defaultdict(lambda: {"n": 0, "ok": 0, "bytes_ok": []})
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if "kind" not in r or "error" in r:
            continue
        k = per[r["kind"]]
        k["n"] += 1
        if r.get("ok"):
            k["ok"] += 1
            k["bytes_ok"].append(r["raw_bytes"])
    return {
        kind: {
            "n": v["n"], "ok": v["ok"],
            "bytes_ok_median": int(st.median(v["bytes_ok"])) if v["bytes_ok"] else None,
        }
        for kind, v in sorted(per.items())
    }


def main() -> int:
    drivers = {}
    for arg in sys.argv[1:]:
        label, path = arg.split("=", 1)
        drivers[label] = {"source_battery": Path(path).name, "kinds": summarize(path)}
    OUT.write_text(json.dumps({
        "note": ("output bytes per successful task (whole trace) + single-shot "
                 "ok-rates, per driver; ratchet gates in tests/test_output_budget.py"),
        "template_hash": template_hash(),
        "ok_noise_band": 3,      # per-kind rerun variance measured 2026-07-18
        "bytes_tolerance": 0.10,  # median bytes/success may not RISE beyond this
        "drivers": drivers,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} (templates {template_hash()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
