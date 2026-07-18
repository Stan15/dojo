"""Judged spot-set: blind pairwise QUALITY comparison of two arms' outputs.

The shape story (ok-rates, bytes) is measured by measure.py/analyze.py; this
answers the remaining decision-rule question — did CONTENT quality hold? It
takes two battery jsonls (same driver, same scenarios), samples scenarios
where BOTH arms produced parseable JSON, recompiles each scenario's real task
prompt for context, and asks a cheap codex judge which output serves the
learner better, blind (A/B order randomized per pair, recorded).

Usage:
  python spot_judge.py A.jsonl B.jsonl labelA labelB out.jsonl [n] [seed]
Judge driver (owner-authorized, sparingly):
  codex exec -c model_reasoning_effort=low --skip-git-repo-check -s read-only
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
from pathlib import Path

from dojo.evals.runner import CORPUS_DIR, compile_step, seed_store, run_command
from dojo.tasks import service

sys.path.insert(0, str(Path(__file__).parent))
from measure import json_span  # noqa: E402

JUDGE_CMD = ("codex exec -c model_reasoning_effort=low "
             "--skip-git-repo-check -s read-only")

JUDGE_PROMPT = """Two AI systems answered the same tutoring task. Judge which
OUTPUT serves the learner better on CONTENT quality only: pedagogical value,
correctness, specificity, calibration to the task. Ignore formatting,
verbosity style, and field order — both already validated.

## TASK GIVEN TO BOTH
{task}

## OUTPUT A
{a}

## OUTPUT B
{b}

Your final output is exactly this JSON (anything before it is ignored):
{{"winner": "A", "reason": "one sentence"}}
"winner" is exactly one of A, B, tie."""


def load_payloads(path: str) -> dict[str, dict]:
    """scenario -> first driven row with a parseable JSON payload."""
    out: dict[str, dict] = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if "kind" not in r or "error" in r or r["scenario"] in out:
            continue
        span = json_span(r.get("raw", ""))
        if span:
            r["_payload"] = r["raw"][span[0]:span[1]]
            out[r["scenario"]] = r
    return out


def task_prompt(scenario: str) -> str | None:
    import yaml
    path = CORPUS_DIR / "quality" / f"{scenario}.yaml"
    sc = yaml.safe_load(path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        store = seed_store(Path(td), sc["seed"])
        cid = sc["seed"]["campaign"]["id"]
        for step in sc["steps"]:
            compiled = compile_step(store, cid, step["compile"])
            if "respond_with" in step:
                if not service.submit(store, service.emit(store, compiled).id,
                                      json.dumps(step["respond_with"])).ok:
                    return None
                continue
            return service.emit(store, compiled).prompt
    return None


def main() -> int:
    fa, fb, la, lb, out_path = sys.argv[1:6]
    n = int(sys.argv[6]) if len(sys.argv) > 6 else 10
    rng = random.Random(int(sys.argv[7]) if len(sys.argv) > 7 else 7)
    pa, pb = load_payloads(fa), load_payloads(fb)
    common = sorted(set(pa) & set(pb))
    # spread across kinds for category coverage
    by_kind: dict[str, list[str]] = {}
    for s in common:
        by_kind.setdefault(pa[s]["kind"], []).append(s)
    picks: list[str] = []
    while len(picks) < min(n, len(common)) and any(by_kind.values()):
        for k in sorted(by_kind):
            if by_kind[k] and len(picks) < n:
                picks.append(by_kind[k].pop(rng.randrange(len(by_kind[k]))))
    rows = []
    for s in picks:
        task = task_prompt(s)
        if task is None:
            continue
        first_is_a = rng.random() < 0.5
        x, y = (pa[s], pb[s]) if first_is_a else (pb[s], pa[s])
        prompt = JUDGE_PROMPT.format(task=task[:4000],
                                     a=x["_payload"][:2500], b=y["_payload"][:2500])
        raw = run_command(JUDGE_CMD, prompt, 300)
        span = json_span(raw)
        verdict = json.loads(raw[span[0]:span[1]]) if span else {"winner": "?"}
        w = verdict.get("winner", "?")
        mapped = {"A": la if first_is_a else lb,
                  "B": lb if first_is_a else la}.get(w, w)
        rows.append({"scenario": s, "kind": pa[s]["kind"], "winner": mapped,
                     "order_first": la if first_is_a else lb,
                     "reason": verdict.get("reason", "")})
        Path(out_path).write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
        print(f"[{len(rows)}] {s}: {mapped}", flush=True)
    from collections import Counter
    print("VERDICTS:", dict(Counter(r["winner"] for r in rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
