"""Deterministic trap-avoidance scoring for the 6i A/B grid (scratch).

Each deliberation-trap scenario's WRONG answer is field-detectable, so
local cells need no judge. Per row: AVOIDED / HIT / REJECT (shape-fail
— neither, but reported) / JUDGE_ONLY (gen_collision: collision
compliance is not cleanly mechanical; the codex spot cell covers it).

Usage: python scratch/prompt-lab/trap_check.py <battery.jsonl> [...]
Prints per-file: avoided/hit/reject counts + per-scenario verdicts.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "scratch/token-diet")
from measure import json_span  # noqa: E402


def payload_json(raw: str):
    span = json_span(raw)
    if not span:
        return None
    try:
        return json.loads(raw[span[0]:span[1]])
    except Exception:
        return None


def verdict(scenario: str, row: dict):
    raw = row.get("raw", "") or ""
    out = payload_json(raw)
    if not row.get("ok") or out is None:
        return "REJECT"
    s = scenario
    if s.startswith("grade_"):
        score = out.get("score")
        if score is None:
            return "REJECT"
        if score <= 0.5 and out.get("error_tag"):
            return "AVOIDED"
        return "HIT" if score >= 0.7 else "PARTIAL"
    if s == "reflect_topic_split_masked_by_aggregate_nav":
        strat = out.get("strategy")
        lowered = bool(strat) and strat.get("difficulty") == "beginner"
        scoped = any("sight" in str(i.get("key", "")) + str(i.get("text", ""))
                     for i in out.get("insight_updates", []))
        if lowered:
            return "HIT"
        return "AVOIDED" if scoped else "PARTIAL"
    if s == "reflect_fast_wrong_inflates_difficulty_chess":
        strat = out.get("strategy")
        lowered = bool(strat) and strat.get("difficulty") == "beginner"
        retired = bool(out.get("topic_retirements"))
        if lowered or retired:
            return "HIT"
        rushing = any(re.search(r"rush|fast|second|quick|calculat", str(i.get("text", "")), re.I)
                      for i in out.get("insight_updates", []))
        return "AVOIDED" if rushing else "PARTIAL"
    if s.startswith("route_lexical_"):
        good_camp = {"route_lexical_crane_rigging_vs_ornithology": "field-ornithology",
                     "route_lexical_bass_guitar_vs_angling": "freshwater-angling"}
        bad_camp = {"route_lexical_crane_rigging_vs_ornithology": "crane-operator-prep",
                    "route_lexical_bass_guitar_vs_angling": "bass-guitar-foundations"}
        camp = str(out.get("campaign") or "")
        if bad_camp[s] in camp or camp in bad_camp[s]:
            return "HIT"
        if good_camp[s] in camp or camp in good_camp[s]:
            return "AVOIDED"
        return "PARTIAL"  # stay_inbox / propose_campaign / other
    if s.startswith("plan_deadline_cuts_dependency_root_"):
        roots = {"plan_deadline_cuts_dependency_root_celestial": r"(time|almanac|chronometer)",
                 "plan_deadline_cuts_dependency_root_sourdough": r"(starter|ferment|microb)"}
        paths = " ".join(str(t.get("path", "")) for t in out.get("topics", []))
        return "AVOIDED" if re.search(roots[s], paths) else "HIT"
    if s.startswith("diag_implied_axis_"):
        axes = {"diag_implied_axis_italian_oral": r"(spok|speak|aloud|listen|conversa|oral)",
                "diag_implied_axis_whiteboard_interview": r"(hand|whiteboard|paper|trace|without (running|execut)|no (ide|autocomplete))"}
        prompts = " ".join(str(i.get("prompt", "")) for i in out.get("items", []))
        return "AVOIDED" if re.search(axes[s], prompts, re.I) else "HIT"
    if s.startswith("gen_collision_"):
        return "JUDGE_ONLY"
    return "UNKNOWN"


def main() -> int:
    for f in sys.argv[1:]:
        rows = [json.loads(l) for l in Path(f).read_text().splitlines() if l.strip()]
        counts: dict[str, int] = {}
        details = []
        pre = []
        for r in rows:
            if "error" in r:
                counts["INFRA"] = counts.get("INFRA", 0) + 1
                continue
            v = verdict(r["scenario"], r)
            counts[v] = counts.get(v, 0) + 1
            details.append(f"  {v:10} {r['scenario']}")
            if isinstance(r.get("pre_bytes"), int):
                pre.append(r["pre_bytes"])
        print(f"== {Path(f).name}: {counts}  pre_bytes median={sorted(pre)[len(pre)//2] if pre else '?'}")
        for d in sorted(details):
            print(d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
