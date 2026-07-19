"""R3-LFM adjudication: arm A (blind resample) vs arm B (error feedback) on
lfm2.5-thinking:1.2b grade/route stems. Decision rule (pre-registered):
B budget-success >= A+15 points OR B mean-subs <= A-0.5 -> QUESTIONS
proposal for retry enrichment; else the negative result stands for this rep.

    python scratch/prompt-lab/r3lfm_adjudicate.py
"""
import json
from pathlib import Path

B = Path("scratch/token-diet/baselines")
for arm in ("A", "B"):
    p = B / f"retryprobe_lfmthink_{arm}.jsonl"
    if not p.exists():
        print(f"arm {arm}: no file yet")
        continue
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    ok = sum(1 for r in rows if r.get("ok"))
    subs = [r["submissions"] for r in rows if "submissions" in r]
    n = len(rows)
    print(f"arm {arm}: {ok}/{n} budget-ok ({100*ok/max(1,n):.0f}%), "
          f"mean subs {sum(subs)/max(1,len(subs)):.2f}")
