"""Token-diet measurement harness (scratch; never ships).

Runs the VISIBLE quality corpus through the production compile→fulfill→submit
path with a given driver command, one shot per driven step (no retries), and
records where the output bytes actually go:

  raw_bytes        — everything the model emitted
  json_bytes       — the emitted final-JSON span (as formatted by the model)
  json_min_bytes   — the same object re-serialized compact (whitespace floor)
  pre_bytes        — bytes before the final JSON span (deliberation/preamble)
  ok / errors      — validation outcome (single-shot)
  secs             — wall latency

Usage: python measure.py "<driver command>" out.jsonl [name_filter ...]
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

from dojo.evals.runner import CORPUS_DIR, compile_step, seed_store, submit_canned, run_command
from dojo.tasks import service

import yaml


def json_span(raw: str):
    """Locate the last balanced, parseable top-level {...} span in raw.
    Forward scan, string-aware. Returns (start, end) or None."""
    spans = []
    depth = 0
    in_str = False
    esc = False
    start = None
    for i, c in enumerate(raw):
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    spans.append((start, i + 1))
                    start = None
    for s, e in reversed(spans):
        try:
            json.loads(raw[s:e])
            return s, e
        except Exception:
            continue
    return None


def run_scenario(path: Path, driver: str) -> list[dict]:
    rows: list[dict] = []
    sc = yaml.safe_load(path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        try:
            store = seed_store(Path(td), sc["seed"])
        except Exception as exc:
            return [{"scenario": path.stem, "error": f"seed: {exc}"}]
        profile = os.environ.get("DOJO_ANCHOR_PROFILE")
        if profile:  # A/B arm switch (QUESTIONS 6i): compiler-side, per seeded store
            store.configs.set_value("fulfiller.anchor_profile", profile)
        rprofile = os.environ.get("DOJO_ROUTE_PROFILE")
        if rprofile:  # RSIMP arm switch: lean route rules, compiler-side
            store.configs.set_value("fulfiller.route_profile", rprofile)
        rskel = os.environ.get("DOJO_ROUTE_SKELETON")
        if rskel:  # RFIX3 arm switch: live-interpolated route skeleton
            store.configs.set_value("fulfiller.route_skeleton", rskel)
        cid = sc["seed"]["campaign"]["id"]
        for idx, step in enumerate(sc["steps"]):
            try:
                compiled = compile_step(store, cid, step["compile"])
            except Exception as exc:
                rows.append({"scenario": path.stem, "step": idx, "error": f"compile: {exc}"})
                break
            if "respond_with" in step:
                outcome = submit_canned(store, compiled, step["respond_with"])
                if not outcome.ok:
                    rows.append({"scenario": path.stem, "step": idx,
                                 "error": f"canned rejected: {outcome.errors[:2]}"})
                    break
                continue
            task = service.emit(store, compiled)
            t0 = time.monotonic()
            try:
                raw = run_command(driver, task.prompt, 240)
            except Exception as exc:
                rows.append({"scenario": path.stem, "step": idx, "kind": compiled.kind,
                             "error": f"driver: {str(exc)[:120]}"})
                break
            secs = time.monotonic() - t0
            outcome = service.submit(store, task.id, raw)
            span = json_span(raw)
            raw_b = len(raw.encode("utf-8"))
            if span:
                s, e = span
                body = raw[s:e]
                json_b = len(body.encode("utf-8"))
                pre_b = len(raw[:s].encode("utf-8"))
                try:
                    json_min_b = len(json.dumps(json.loads(body), separators=(",", ":"),
                                                ensure_ascii=False).encode("utf-8"))
                except Exception:
                    json_min_b = None
            else:
                json_b = pre_b = json_min_b = None
            rows.append({
                "scenario": path.stem, "step": idx, "kind": compiled.kind,
                "prompt_bytes": task.payload_bytes,
                "raw_bytes": raw_b, "json_bytes": json_b,
                "json_min_bytes": json_min_b, "pre_bytes": pre_b,
                "ok": outcome.ok,
                **({"errors": outcome.errors[:3]} if not outcome.ok else {}),
                "secs": round(secs, 1),
                "raw": raw[:6000],
            })
            if not outcome.ok:
                break  # downstream steps depend on applied state
    return rows


def main() -> int:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    driver = sys.argv[1]
    out_path = Path(sys.argv[2])
    workers = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 1
    filters = sys.argv[4:] if workers else sys.argv[3:]
    scenarios = sorted((CORPUS_DIR / "quality").glob("*.yaml"))
    if filters:
        scenarios = [p for p in scenarios if any(f in p.stem for f in filters)]
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(run_scenario, p, driver): p for p in scenarios}
        for fut in as_completed(futs):
            rows.extend(fut.result())
            out_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                                encoding="utf-8")
            print(f"[{len(rows)} rows] {futs[fut].stem}", flush=True)
    done = [r for r in rows if "error" not in r]
    ok = [r for r in done if r["ok"]]
    print(f"DONE driver={driver!r}: {len(done)} driven steps, {len(ok)} ok, "
          f"{len(rows)-len(done)} infra-errors", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
