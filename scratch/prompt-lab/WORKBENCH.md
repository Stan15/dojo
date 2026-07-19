# PROMPT LAB WORKBENCH — live campaign state

_Directive: docs/PROMPT_LAB.md. This file is the resumption point: a fresh
or woken session reads the directive, then this, then executes NEXT._

## Phase

BOOTSTRAP (2026-07-19, ~00:40): finishing the drop-diagnosis pipeline
before the open-ended loop starts.

## NEXT (exact order)

1. FIX letter-path bleed (pre-registered below): campaign_plan.md rule 1 +
   Check — remove ALL abstract letter-path literals beyond the skeleton's
   single "a.b.c"; state depth/merge rule in WORDS ("when one more level
   would exceed the cap, merge the extra idea into the leaf with an
   underscore — never add a level past {{ topic_depth }}").
2. rm evals/baselines/token-footprint.json && pytest tests/test_token_footprint.py
   (regenerate; review diff — plan bytes shift slightly).
3. Mini-batteries, PLAN SCENARIOS ONLY, one at a time (filters are argv
   after workers count): 
   python scratch/token-diet/measure.py "python scratch/token-diet/api_driver.py gemma3:4b" scratch/token-diet/baselines/iterW2_gemma3_4b_plan.jsonl 3 plan_ deadline_compression vague_goal
   then same for qwen3.5:4b --no-think → iterW2_qwen35_4b_plan.jsonl.
4. Splice: replace campaign.plan rows in iterW_*.jsonl with iterW2 rows →
   write iterW2_<model>.jsonl combined (note in this file). Then
   python scratch/token-diet/build_output_budget.py \
     "api-chat/qwen3.5:4b/--no-think=scratch/token-diet/baselines/iterW2_qwen35_4b.jsonl" \
     "api-chat/gemma3:4b=scratch/token-diet/baselines/iterW2_gemma3_4b.jsonl"
   → full pytest → COMMIT 2 (templates+compiler+tests+goldens+footprint+
   output-budget; message: drop-diagnosis template iteration; note the
   caught-and-fixed letter-bleed regression).
   (gemma speed probe optional, after commit — nice-to-have only.)
4. COMMIT 3: cp scratchpad route_url_bleed_near_empty_registry.yaml →
   src/dojo/evals/corpus/quality/; ratchet tests/test_quality_corpus.py
   (MIN_TOTAL 79→80, routing 7→8, dated comment); pytest; commit.
5. README demo retry (script: scratchpad/readme_demo_retry.py, verified
   with canned driver): qwen3.5:4b --no-think then gemma3:4b, ≤2 budgets
   each via api_driver. If a 4B lands a GOOD reflect (content, not just
   shape): update README demo with exact model tag; else record honestly.
6. CODEX VALIDATION (owner-authorized 2026-07-19): one full `-m eval -q`
   with the standard codex driver; expect the five dropped floors to
   recover + new-scenario floors to bootstrap; update ratchets SAME
   commit. Read new traces → feed loop step 1.
7. STATE.md item 11 + QUESTIONS board update (drafts in scratchpad:
   state_draft.md, questions_draft.md).
8. LOOP: start experiment queue (directive §queue) — first: 6i trap
   scenarios (~2/kind, visible) + anchor-profile config + A/B batteries.

## Pre-registered (open)

- **P1 letter-path bleed fix (2026-07-19 ~00:55).** Finding: my rule-1
  rewrite added two abstract letter-path literals (a.b.c.d_e / a.b.c.d.e);
  gemma iterW plan collapsed 5/9→2/9 with 6/7 failures emitting literal
  letter paths (even fused: a.pod_b.service_c.deployment); qwen shows one
  (a.b.c.d_alpha). Mechanism: repetition raised the abstract pattern's
  salience → 4B models copy it as content (README mode 9, self-inflicted).
  Hypothesis: stating the depth/merge rule in WORDS with zero new
  letter-paths removes the bleed without losing the codex-tier depth
  statement. Decision rule: gemma plan ≥5/9 on the mini-battery
  (recovery to iterV level), qwen plan ≥4/9 (was 5/9; ±1 on n=9 tolerated
  only if no letter-path appears in ANY failure), zero letter-path
  outputs across both; codex depth compliance re-verified in the
  authorized validation run (plan_extend_not_duplicate must pass).
  If gemma stays ≤3/9 → revert to a Check-line-only depth statement and
  re-test.

## Results ledger

- iterW qwen3.5:4b battery: 42/72 ok (58%) vs iterV 43/77 (56%) — reflect
  6/22→10/21 (empty-INSIGHTS create-first fix visible), generate 14/15,
  7×240s timeouts (3-way contention, not template regressions).
- qwen3.5:4b single-stream probe (real counters, 7KB reflect payload):
  pp 106 tok/s, gen 7.6 tok/s, 47s total; eval_count ≈ printed bytes
  (no hidden thinking with --no-think).
- plan_extend_not_duplicate passed at 4B under the new depth-stated
  template (hard-failed both codex runs pre-fix). n=1, encouraging only.

## Negative results (never blind-retest)

- (carry-over, dev/token-diet) armACC-in input compression: parked —
  shape-risk × battery-cost, ride-along only.
- (carry-over) SKILL.md trim: only 2% removable; below materiality.

## Spend ledger (codex, this campaign)

- (none yet)

## Contamination log

- This session: CLEAN (holdout untouched; no holdout names/counts in
  context).
