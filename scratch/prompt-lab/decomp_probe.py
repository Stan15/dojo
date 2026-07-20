"""Split-reflect pilot probe (owner-approved 2026-07-20; scratch, never ships).

Per reflect-driving scenario: compile the SAME evidence sections the single
call uses (compiler.reflect_section_values), render the ops/voice pilot
templates, drive the model twice (voice sees call-1's decisions digest),
merge into a full ReflectResult, and submit the merged JSON to a REAL
emitted campaign.reflect task — so validation and apply are the production
path, and only the generation is decomposed.

Rows: scenario, ok, errors, call bytes/secs (prompt+raw per call), merged.

    python scratch/prompt-lab/decomp_probe.py "<driver cmd>" out.jsonl [filters...]
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "scratch/token-diet")

import yaml  # noqa: E402

from dojo import limits  # noqa: E402
from dojo.evals.runner import CORPUS_DIR, seed_store, run_command  # noqa: E402
from dojo.prompts import render  # noqa: E402
from dojo.schemas import ReflectOpsResult, ReflectVoiceResult  # noqa: E402
from dojo.tasks import compiler, service  # noqa: E402
from measure import json_span  # noqa: E402


def caps(kind: str) -> dict:
    return dict(limits.TEMPLATE_CAPS[kind])


def decisions_digest(ops: ReflectOpsResult) -> str:
    lines = []
    for iu in ops.insight_updates:
        d = iu.model_dump() if hasattr(iu, "model_dump") else dict(iu)
        lines.append(f"- insight {d.get('op')}: {d.get('key') or d.get('id')} — "
                     f"\"{(d.get('text') or '')[:80]}\" ({d.get('reason', '')[:60]})")
    if ops.strategy is not None:
        s = ops.strategy.model_dump()
        dial = ", ".join(f"{k}={v}" for k, v in s.items() if k != "reason" and v)
        lines.append(f"- strategy: {dial} ({s.get('reason', '')[:60]})")
    if ops.plan_revision is not None:
        lines.append(f"- plan revised: {ops.plan_revision.reason[:80]}")
    for tr in ops.topic_retirements:
        lines.append(f"- retired {tr.path} ({tr.reason[:60]})")
    return "\n".join(lines) or "(no changes this review — everything held steady)"


def drive(driver: str, prompt: str):
    t0 = time.monotonic()
    raw = run_command(driver, prompt, 240)
    return raw, time.monotonic() - t0


def parse(raw: str, model_cls):
    span = json_span(raw)
    if not span:
        return None, ["no JSON object found"]
    try:
        return model_cls.model_validate(json.loads(raw[span[0]:span[1]])), []
    except Exception as exc:
        return None, [str(exc)[:200]]


def run_scenario(path: Path, driver: str) -> dict:
    sc = yaml.safe_load(path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        store = seed_store(Path(td), sc["seed"])
        cid = sc["seed"]["campaign"]["id"]
        campaign = store.campaigns.get(cid)
        step = next(s for s in sc["steps"] if s.get("compile", {}).get("fn") == "reflect")
        window_n = step["compile"].get("window_n", 15)
        values, context = compiler.reflect_section_values(store, campaign, window_n=window_n)

        ops_prompt = render("campaign_reflect_ops.md",
                            {**caps("campaign.reflect"), **values})
        raw1, s1 = drive(driver, ops_prompt)
        ops, errs = parse(raw1, ReflectOpsResult)
        row = {"scenario": path.stem,
               "call1": {"prompt_bytes": len(ops_prompt.encode()), "raw_bytes": len(raw1.encode()), "secs": round(s1, 1)}}
        if ops is None:
            row.update(ok=False, errors=[f"call1: {e}" for e in errs], raw1=raw1[:4000])
            return row

        voice_prompt = render("campaign_reflect_voice.md", {
            **caps("campaign.reflect"),
            "decisions_digest": decisions_digest(ops),
            "learner_feedback_or_none": values["learner_feedback_or_none"],
            "journal_example": values["journal_example"],
        })
        raw2, s2 = drive(driver, voice_prompt)
        voice, errs2 = parse(raw2, ReflectVoiceResult)
        row["call2"] = {"prompt_bytes": len(voice_prompt.encode()), "raw_bytes": len(raw2.encode()), "secs": round(s2, 1)}
        if voice is None:
            row.update(ok=False, errors=[f"call2: {e}" for e in errs2], raw2=raw2[:4000])
            return row

        merged = {**json.loads(ops.model_dump_json()), **json.loads(voice.model_dump_json())}
        task = service.emit(store, compiler.compile_reflect(store, campaign, window_n=window_n))
        outcome = service.submit(store, task.id, json.dumps(merged, ensure_ascii=False))
        row.update(ok=outcome.ok,
                   **({} if outcome.ok else {"errors": outcome.errors[:3]}),
                   merged_bytes=len(json.dumps(merged).encode()))
        return row


def main() -> int:
    driver, out_path = sys.argv[1], Path(sys.argv[2])
    filters = sys.argv[3:]
    scenarios = sorted((CORPUS_DIR / "quality").glob("*.yaml"))
    if filters:
        scenarios = [p for p in scenarios if any(f in p.stem for f in filters)]
    rows = []
    for p in scenarios:
        try:
            sc = yaml.safe_load(p.read_text())
            if not any(s.get("compile", {}).get("fn") == "reflect" for s in sc.get("steps", [])):
                continue
        except Exception:
            continue
        try:
            rows.append(run_scenario(p, driver))
        except Exception as exc:
            rows.append({"scenario": p.stem, "error": str(exc)[:150]})
        out_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
        print(f"[{len(rows)}] {p.stem} ok={rows[-1].get('ok')}", flush=True)
    ok = sum(1 for r in rows if r.get("ok"))
    print(f"DONE split-reflect: {ok}/{len(rows)} ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
