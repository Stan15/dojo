"""W3 sizing: would normalizing evidence (strip trailing/leading ellipsis and
symmetric wrapping quotes) convert archived verbatim-evidence rejections?

Reads archived battery jsonls + visible corpus yamls (read-only). For every
grade row rejected with a verbatim-evidence error whose raw JSON parses,
re-tests the evidence against every user_answer in that scenario's seed
under (a) raw form, (b) normalized form. Reports convert counts per file.

    python scratch/prompt-lab/evidence_norm_check.py
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import yaml

B = Path("scratch/token-diet/baselines")
C = Path("src/dojo/evals/corpus/quality")

ELLIPSIS = ("...", "…")
QUOTE_PAIRS = [('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’")]


def normalize(ev: str) -> str:
    s = ev.strip()
    changed = True
    while changed:
        changed = False
        for e in ELLIPSIS:
            if s.endswith(e):
                s = s[: -len(e)].rstrip()
                changed = True
            if s.startswith(e):
                s = s[len(e):].lstrip()
                changed = True
        for a, b in QUOTE_PAIRS:
            if len(s) >= 2 and s.startswith(a) and s.endswith(b):
                s = s[1:-1].strip()
                changed = True
    return s


answers_by_scenario: dict[str, list[str]] = {}
for p in C.glob("*.yaml"):
    try:
        sc = yaml.safe_load(p.read_text())
    except Exception:
        continue
    texts = []
    for att in (sc.get("seed") or {}).get("attempts", []) or []:
        ua = att.get("user_answer")
        if isinstance(ua, str):
            texts.append(ua)
    answers_by_scenario[p.stem] = texts

per_file = Counter()
per_file_total = Counter()
examples = []
for p in sorted(B.glob("*.jsonl")):
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("ok") or "error" in r or r.get("kind") != "attempt.grade":
            continue
        if not any("verbatim" in str(e) for e in r.get("errors", [])):
            continue
        per_file_total[p.name] += 1
        m = re.search(r'"evidence"\s*:\s*"((?:[^"\\]|\\.)*)"', r.get("raw", ""))
        if not m:
            continue
        try:
            ev = json.loads('"' + m.group(1) + '"')
        except Exception:
            continue
        answers = answers_by_scenario.get(r["scenario"], [])
        raw_hit = any(ev in a for a in answers)
        norm = normalize(ev)
        norm_hit = norm and any(norm in a for a in answers)
        if not raw_hit and norm_hit:
            per_file[p.name] += 1
            if len(examples) < 8:
                examples.append(f"{p.name}:{r['scenario']}  {ev[:60]!r} -> {norm[:60]!r}")

total_conv = sum(per_file.values())
total_fail = sum(per_file_total.values())
print(f"verbatim-evidence rejections with parseable evidence: {total_fail}; "
      f"CONVERTED by normalization: {total_conv}")
for name, n in per_file.most_common(15):
    print(f"  {n:3} / {per_file_total[name]:3}  {name}")
print("\nexamples:")
for e in examples:
    print(" ", e)
