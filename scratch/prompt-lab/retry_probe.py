"""Retry-feedback probe (R3, scratch; never ships).

Drives quality-corpus scenarios through the PRODUCTION emit->submit path
with the full submission budget, under two retry arms:

  A (resample):  every submission re-sends the original prompt (drain_tasks
                 behavior today — errors never reach a raw driver).
  B (feedback):  submissions after a rejection send the original prompt plus
                 one correction line carrying the rejection errors.

Rows: scenario, arm, submissions_used, ok, errors_per_submission.

Usage:
  python scratch/prompt-lab/retry_probe.py "<driver cmd>" A|B out.jsonl [name_filter ...]
"""
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "src")

import yaml  # noqa: E402

from dojo.evals.runner import CORPUS_DIR, compile_step, seed_store  # noqa: E402
from dojo.tasks import service  # noqa: E402


def run_scenario(path: Path, driver: str, arm: str) -> dict:
    sc = yaml.safe_load(path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        try:
            store = seed_store(Path(td), sc["seed"])
            cid = sc["seed"]["campaign"]["id"]
            compiled = compile_step(store, cid, sc["steps"][0]["compile"])
        except Exception as exc:
            return {"scenario": path.stem, "arm": arm, "error": f"seed/compile: {exc}"}
        task = service.emit(store, compiled)
        errs_log = []
        prompt = task.prompt
        while True:
            try:
                proc = subprocess.run(
                    shlex.split(driver), input=prompt,
                    capture_output=True, text=True, timeout=420,
                )
            except Exception as exc:
                return {"scenario": path.stem, "arm": arm, "error": f"driver: {exc}",
                        "errors_log": errs_log}
            outcome = service.submit(store, task.id, proc.stdout)
            errs_log.append(outcome.errors[:3])
            fresh = store.tasks.get(task.id)
            if outcome.ok or outcome.status != "pending":
                return {"scenario": path.stem, "arm": arm, "ok": outcome.ok,
                        "submissions": fresh.submissions, "errors_log": errs_log}
            if arm == "B":
                joined = "; ".join(outcome.errors[:3])
                prompt = (task.prompt + "\nYour previous output was rejected: "
                          + joined + ". Emit the corrected complete JSON object.")


def main() -> int:
    driver, arm, out_path = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    filters = sys.argv[4:]
    scenarios = sorted((Path(CORPUS_DIR) / "quality").glob("*.yaml"))
    if filters:
        scenarios = [p for p in scenarios if any(f in p.stem for f in filters)]
    rows = []
    for p in scenarios:
        row = run_scenario(p, driver, arm)
        rows.append(row)
        out_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
                            + "\n", encoding="utf-8")
        print(f"[{len(rows)}/{len(scenarios)}] {p.stem}: "
              f"{'ok' if row.get('ok') else row.get('error', 'fail')} "
              f"subs={row.get('submissions', '?')}", flush=True)
    done = [r for r in rows if "error" not in r]
    ok = [r for r in done if r["ok"]]
    subs = [r["submissions"] for r in ok]
    print(f"DONE arm={arm}: {len(ok)}/{len(done)} ok, "
          f"mean subs-to-success={sum(subs)/len(subs):.2f}" if subs else "DONE: none ok",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
