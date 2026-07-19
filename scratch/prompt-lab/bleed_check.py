"""EX-BLEED metric: fraction of driven outputs containing >=N-consecutive-word
spans copied from the compiled payload's skeleton EXAMPLE values (example
bleed, README modes 9/10). Runs over battery jsonls; the example values are
extracted from the corresponding compiled template text at runtime.

    python scratch/prompt-lab/bleed_check.py <battery.jsonl> [min_span_words]

Reports per-kind bleed rate + the offending spans. Used by the EX-BLEED
pre-registration (WORKBENCH) to measure the baseline before any
content-orthogonal example arm, and the arm itself after.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")

from dojo.prompts import all_templates  # noqa: E402

MIN_SPAN = int(sys.argv[2]) if len(sys.argv) > 2 else 5


def example_values(template_text: str) -> list[str]:
    """String literals that appear as VALUES inside the skeleton block(s)."""
    vals = []
    for m in re.finditer(r':\s*"((?:[^"\\]|\\.){10,300})"', template_text):
        v = m.group(1)
        if "{{" in v:  # interpolation placeholder, not a literal example
            continue
        vals.append(v)
    return vals


def spans(text: str, n: int):
    words = text.lower().split()
    for i in range(len(words) - n + 1):
        yield " ".join(words[i: i + n])


def main() -> int:
    battery = Path(sys.argv[1])
    tmpl_examples = {name: example_values(text) for name, text in all_templates().items()}
    per_kind = {}
    offenders = []
    for line in battery.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if "kind" not in r or "error" in r:
            continue
        kind = r["kind"]
        per_kind.setdefault(kind, [0, 0])
        per_kind[kind][1] += 1
        raw = r.get("raw", "").lower()
        hit = None
        for name, vals in tmpl_examples.items():
            for v in vals:
                for sp in spans(v, MIN_SPAN):
                    if sp in raw:
                        hit = (name, sp)
                        break
                if hit:
                    break
            if hit:
                break
        if hit:
            per_kind[kind][0] += 1
            offenders.append(f"{r['scenario']} [{kind}] <- {hit[0]}: \"{hit[1]}\"")
    for kind, (b, n) in sorted(per_kind.items()):
        print(f"{kind}: bleed {b}/{n}")
    for o in offenders[:15]:
        print(" ", o)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
