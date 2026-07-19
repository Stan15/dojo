"""W5 verification: replay archived verbatim rejections through the proposed
longest-true-substring rescue and report (a) converts, (b) any answer-KEY
quote that would slip through — the guard-regression check (MUST be zero).

Proposed rule (mirrors the pre-registration): normalized evidence vs each
learner answer; find the longest contiguous common substring; accept iff
core_len >= max(0.7 * len(evidence_norm), MIN_CORE_CHARS) and the core has
>= MIN_CORE_WORDS words; the STORED evidence is the core (learner's words).

    python scratch/prompt-lab/evidence_core_check.py
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

import yaml

MIN_CORE_WORDS = 3
MIN_CORE_CHARS = 12
RATIO = 0.7


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip().lower()


def core_rescue(evidence: str, answers: list[str]):
    ev = norm(evidence)
    if not ev:
        return None
    best = ""
    for a in answers:
        an = norm(a)
        m = difflib.SequenceMatcher(None, ev, an).find_longest_match(0, len(ev), 0, len(an))
        if m.size > len(best):
            best = ev[m.a: m.a + m.size]
    core = best.strip()
    if (len(core) >= max(RATIO * len(ev), MIN_CORE_CHARS)
            and len(core.split()) >= MIN_CORE_WORDS):
        return core
    return None


def main() -> int:
    ans, keys = {}, {}
    for p in Path("src/dojo/evals/corpus/quality").glob("*.yaml"):
        try:
            sc = yaml.safe_load(p.read_text())
        except Exception:
            continue
        seed = sc.get("seed") or {}
        ans[p.stem] = [a.get("user_answer") for a in seed.get("attempts", []) or []
                       if isinstance(a.get("user_answer"), str)]
        keys[p.stem] = [ex.get("answer") for ex in seed.get("exercises", []) or []
                        if isinstance(ex.get("answer"), str)]

    converts = guard_breaches = total = 0
    examples = []
    for p in Path("scratch/token-diet/baselines").glob("*.jsonl"):
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("ok") or "error" in r or r.get("kind") != "attempt.grade":
                continue
            if not any("verbatim" in str(e) for e in r.get("errors", [])):
                continue
            m = re.search(r'"evidence"\s*:\s*"((?:[^"\\]|\\.)*)"', r.get("raw", ""))
            if not m:
                continue
            try:
                ev = json.loads('"' + m.group(1) + '"')
            except Exception:
                continue
            A = ans.get(r["scenario"], [])
            if any(norm(ev) in norm(a) for a in A):
                continue  # W3-class, already handled
            total += 1
            core = core_rescue(ev, A)
            if core:
                converts += 1
                if len(examples) < 6:
                    examples.append(f"{r['scenario']}: {ev[:50]!r} -> core {core[:50]!r}")
                # guard check: is the ACCEPTED core also a key quote?
                if any(norm(core) in norm(k) for k in keys.get(r["scenario"], []) if k):
                    # core is learner-substring by construction; overlap with the
                    # key only matters if it is NOT in any learner answer — it is,
                    # so this cannot fire; belt-and-braces count anyway
                    guard_breaches += 1

    print(f"post-W3 verbatim rejections replayed: {total}")
    print(f"W5 core-rescue converts: {converts}")
    print(f"guard breaches (accepted evidence not truly learner-substring): {guard_breaches}")
    for e in examples:
        print(" ", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
