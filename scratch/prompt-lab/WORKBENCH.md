# PROMPT LAB WORKBENCH — live campaign state

_Directive: docs/PROMPT_LAB.md. This file is the resumption point: a fresh
or woken session reads the directive, then this, then executes NEXT._

## Phase

BOOTSTRAP (2026-07-19, ~00:40): finishing the drop-diagnosis pipeline
before the open-ended loop starts.

## NEXT (exact order)

1. WAIT: gemma3:4b battery in flight (bkbns7z5h → scratch/token-diet/
   baselines/iterW_gemma3_4b.jsonl). ONE battery at a time; tree quiet.
2. On completion: gemma single-stream speed probe (pp/gen counters, same
   probe as qwen: reflect payload via /api/chat, think field n/a).
3. python scratch/token-diet/build_output_budget.py \
     "api-chat/qwen3.5:4b/--no-think=scratch/token-diet/baselines/iterW_qwen35_4b.jsonl" \
     "api-chat/gemma3:4b=scratch/token-diet/baselines/iterW_gemma3_4b.jsonl"
   → full pytest → COMMIT 2 (templates+compiler+tests+goldens+footprint+
   output-budget; message: drop-diagnosis template iteration).
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

- (none yet — register before each test, see directive §loop step 3)

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
