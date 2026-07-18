"""Aggregate measure.py outputs: where do the bytes go, per kind × driver."""
import json
import statistics as st
import sys
from pathlib import Path
from collections import defaultdict


def load(p):
    rows = []
    for line in Path(p).read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def pct(a, b):
    return f"{100*a/b:.0f}%" if b else "-"


def main():
    for path in sys.argv[1:]:
        rows = load(path)
        driven = [r for r in rows if "kind" in r and "error" not in r]
        infra = [r for r in rows if "error" in r]
        print(f"\n=== {Path(path).name}: {len(driven)} driven steps, {len(infra)} infra-errors")
        by_kind = defaultdict(list)
        for r in driven:
            by_kind[r["kind"]].append(r)
        print(f"{'kind':<22}{'n':>3}{'ok':>5}{'raw_md':>8}{'json_md':>8}{'min_md':>8}"
              f"{'ws%':>5}{'pre_md':>8}{'pre_max':>8}{'secs':>6}")
        for kind, rs in sorted(by_kind.items()):
            ok = [r for r in rs if r["ok"]]
            js = [r["json_bytes"] for r in rs if r.get("json_bytes")]
            jm = [r["json_min_bytes"] for r in rs if r.get("json_min_bytes")]
            pre = [r["pre_bytes"] for r in rs if r.get("pre_bytes") is not None]
            raws = [r["raw_bytes"] for r in rs]
            ws = (1 - st.median(jm) / st.median(js)) * 100 if js and jm else 0
            print(f"{kind:<22}{len(rs):>3}{pct(len(ok), len(rs)):>5}"
                  f"{st.median(raws):>8.0f}{st.median(js) if js else 0:>8.0f}"
                  f"{st.median(jm) if jm else 0:>8.0f}{ws:>4.0f}%"
                  f"{st.median(pre) if pre else 0:>8.0f}{max(pre) if pre else 0:>8.0f}"
                  f"{st.median([r['secs'] for r in rs]):>6.0f}")
        # error taxonomy
        errs = defaultdict(int)
        for r in driven:
            for e in r.get("errors", []):
                errs[e[:70]] += 1
        if errs:
            print("  top rejections:")
            for e, n in sorted(errs.items(), key=lambda kv: -kv[1])[:8]:
                print(f"    {n:>2}× {e}")


if __name__ == "__main__":
    main()
