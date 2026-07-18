# Token-diet campaign — final report (dev/token-diet, 2026-07-17→18)

**Verdict: shipped-on-branch as `armJ5S` — shape-hardened templates +
semantic-only validation, gated in both directions. Owner merge gate is the
remaining step.** (4-scenario codex bootstrap recheck: see addendum.)

## What changed

1. **Templates (all 7 kinds):** realistic cap-compliant literal skeleton
   values (no `a|b|c` enum strings, no `//` comments, no `"..."`); option
   lists + per-variant required fields in prose "Field rules" blocks; TWO
   complete examples where items repeat; example values de-bled (no id-like
   tokens, no cap-breaking length, skills marked as placeholders);
   required fields first in example field order.
2. **Validation (armS):** grade `evidence` word-cap rejection dropped
   (verbatim-substring hallucination guard stays hard; storage clipped at
   3× cap); rubric list→string coercion; plan topic summary clip-not-reject.
3. **Gates (both directions, permanent):** shape-lints in test_prompts.py
   reject the measured hostile patterns; test_semantic_validation.py pins
   the armS behaviors; prompts.md rule 7 rewritten + §1c; goldens/footprint
   re-pinned; guard README beside the templates (progressive-disclosure
   chain from CLAUDE.md/AGENTS.md/CLAUDE_START.md). 722 tests green.

## Results (same-driver, ok per 64 single-shot; base replicates where run)

| model | base | final (armJ5S-era runs) |
|---|---|---|
| qwen3.5:4b (class verdict) | 30/24/25 (26.3±3.2) | 33, **35** (armJS, armJ4S) |
| gemma3:4b | 28 | 53, 50 |
| lfm2.5-1.2b | 11 | 21, 21 |
| qwen3.5:0.8b / gemma3:1b | 2 / 0 | 2 / 0 (floors — capability-bound) |

- Single-shot failure rate at gemma4b: **56% → 17%**; production retry
  multiplier (max 3 submissions) ≈ 1.87 → 1.20 expected submissions per
  success — **~36% whole-trace cost cut** on top of similar per-shot bytes.
- Per-success output bytes (matched-kind medians, class verdict): grade
  −23%, plan −21%, reflect −32%, generate −5% (whitespace + tighter prose;
  compare per kind — aggregate medians shift with pass composition).
- **Determinism bonus:** run-to-run sd at class verdict 3.2 → 0.6; worst
  arm run beats the base mean.
- Input-side cost: compiled prompts +11% (Field rules + second examples) —
  repaid by retry elimination at weak tiers; a pure cost (~300B/call) at
  strong tiers. Input-side compression is queued in the accumulate batch.

## Quality proofs

- Blind codex spot-set (10 scenarios, kind-spread): base 5 / arm 4 / tie 1 —
  parity.
- Authorized codex eval run: 64/64 baselined scenarios passed their
  ratchet floors. 4 newer scenarios (no committed floor) scored zero →
  investigated: example-value content bleed (skills skewed toward the
  examples; plan_revision-null anchored) — confirmed FREE from battery
  distributions, fixed in armJ4/armJ5 (skill spread re-centered: gemma4b
  recall+explain 58% → 40%, base 24%; produce back to base share).
- Skill/action distribution check: pass post-armJ4 (residual mild recall
  elevation documented).

## Principles established (now in src/dojo/prompts/README.md, lint-backed)

1-8 as measured (enum-echo, //-comments, quote-wording, evidence-as-
analysis, multiline bait, numeric rumination bait, understatement,
reasoning-neutral anchors) plus the campaign's central discovery:
**9. example values anchor EVERYTHING — length, format, field presence,
and content distribution. Demonstrate compliance; never describe it; keep
example content orthogonal to real decisions (no id-like tokens, skills
are placeholders); required fields first (weak models truncate tails).**

## Honest limitations

- **lfm reflect 7/20→0/20 is a vacuous-pass artifact, not a regression:**
  all 7 base passes were empty-op no-ops (rule 1 adjudicates nothing);
  the demonstrative skeleton makes lfm attempt adjudication beyond its
  1.2B capability. Zero real adjudications under both. Retries-vs-vacuity
  trade is the owner's call at the merge gate.
- goal.route n=1: flaky across all arms (semantic judgment miss).
- 1B floors (gemma3:1b 0-2, qwen3.5:0.8b 1-2): completeness capability,
  not shape — the product floor remains the 4B class, as designed.
- Driver rulings (measurement + product-docs): `ollama run` piped is
  corrupt on ≥0.32 (use the API); think=false binds only via /api/chat;
  old qwen3 needs a soft-switch (deferred). Fulfiller docs deliverable.

## Spend ledger (codex)

- 68-scenario eval run ×1 (pre-authorized) · 10-scenario blind spot-set ×1
  · 4-scenario bootstrap recheck ×1 (QUESTIONS #0 default). Everything
  else ran on local ollama.

## Deferred to the accumulate batch (owner rule: sound-but-marginal)

ArmA compact-JSON anchoring · ArmD omit-null-fields note · SKILL.md trim
(max 2% found) · input-side Field-rules compression · apply_armS.py
idempotency · qwen3:4b think-off robustness point · output-budget ratchet
implementation (evals/baselines/output-budget.json + opt-in marker —
drafts/test_output_budget.py).

## Reproducibility

Every measured tree + results battery is an arm-snapshot commit on
dev/token-diet; `git log --oneline` narrates the campaign;
`scratch/token-diet/{measure,analyze,watch,shape_lint,spot_judge}.py` are
the instruments; hypotheses.md holds the pre-registered decision rule.
