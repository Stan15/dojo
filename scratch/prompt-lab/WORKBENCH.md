# PROMPT LAB WORKBENCH — live campaign state

_Directive: docs/PROMPT_LAB.md. This file is the resumption point: a fresh
or woken session reads the directive, then this, then executes NEXT._

## Phase

BOOTSTRAP (2026-07-19, ~01:15): finishing the drop-diagnosis pipeline
before the open-ended loop starts. P1 fix APPLIED to campaign_plan.md
(words-only depth rule); its verification mini-battery is IN FLIGHT.

## IN-FLIGHT + WORKING-TREE INVENTORY (a resuming session reads this first)

- **Mini-battery possibly running**: gemma3:4b plan-only →
  scratch/token-diet/baselines/iterW2_gemma3_4b_plan.jsonl (9 scenarios).
  Check `pgrep -f measure.py` AND the file's mtime. If the process is
  GONE and the file has <9 scenario rows or is stale, RERUN:
  python scratch/token-diet/measure.py "python scratch/token-diet/api_driver.py gemma3:4b" scratch/token-diet/baselines/iterW2_gemma3_4b_plan.jsonl 3 plan_ deadline_compression
  (Requires ollama serve: `pkill -f "ollama serve"; OLLAMA_NUM_PARALLEL=4
  OLLAMA_MAX_LOADED_MODELS=1 nohup ollama serve >/tmp/ollama-serve.log 2>&1 &`)
- **Uncommitted working tree = COMMIT 2 material, deliberately held** by
  the test_output_budget same-commit gate (template hash vs baseline):
  src/dojo/prompts/{attempt_grade,campaign_plan,campaign_reflect,
  exercise_diagnostic,exercise_generate}.md · 6 new fragments under
  src/dojo/prompts/fragments/ (calibration_*, encounter_*, reflect_ops_*)
  · src/dojo/tasks/compiler.py (branches) · tests/test_prompts.py ·
  tests/test_task_compiler.py · tests/golden/* (2) ·
  evals/baselines/token-footprint.json. Commit them ONLY at NEXT step 4
  (after splice + build_output_budget makes the suite green).
- **evals/baselines/*__holdout*.json modification: OWNER-ONLY. Never
  read/diff/commit/discard. Stage by name only.**
- Session artifacts now IN-REPO (this dir): readme_demo_retry.py,
  draft_route_url_bleed_near_empty_registry.yaml, draft_state_item11.md,
  draft_questions_updates.md.

## NEXT (exact order)

1. DONE ~01:05 — letter-bleed fix applied to campaign_plan.md (words-only
   rule; zero abstract letter-paths beyond the skeleton's single "a.b.c").
2. DONE ~01:08 — footprint regenerated (plan 3150→3316, deliberate).
3. Mini-batteries, PLAN SCENARIOS ONLY, one at a time (filters are argv
   after workers count): 
   python scratch/token-diet/measure.py "python scratch/token-diet/api_driver.py gemma3:4b" scratch/token-diet/baselines/iterW2_gemma3_4b_plan.jsonl 3 plan_ deadline_compression vague_goal
   then same for qwen3.5:4b --no-think → iterW2_qwen35_4b_plan.jsonl.
4. Splice (small python: read iterW_<model>.jsonl, drop rows with
   kind=="campaign.plan", append all rows from iterW2_<model>_plan.jsonl)
   → write iterW2_<model>.jsonl combined (note result here). Then
   python scratch/token-diet/build_output_budget.py \
     "api-chat/qwen3.5:4b/--no-think=scratch/token-diet/baselines/iterW2_qwen35_4b.jsonl" \
     "api-chat/gemma3:4b=scratch/token-diet/baselines/iterW2_gemma3_4b.jsonl"
   → full pytest → COMMIT 2 (templates+compiler+tests+goldens+footprint+
   output-budget; message: drop-diagnosis template iteration; note the
   caught-and-fixed letter-bleed regression).
   (gemma speed probe optional, after commit — nice-to-have only.)
4b. COMMIT 3: cp scratch/prompt-lab/draft_route_url_bleed_near_empty_registry.yaml
   → src/dojo/evals/corpus/quality/route_url_bleed_near_empty_registry.yaml; ratchet tests/test_quality_corpus.py
   (MIN_TOTAL 79→80, routing 7→8, dated comment); pytest; commit.
5. README demo retry (script: scratch/prompt-lab/readme_demo_retry.py,
   verified with canned driver; run from repo root): qwen3.5:4b --no-think then gemma3:4b, ≤2 budgets
   each via api_driver. If a 4B lands a GOOD reflect (content, not just
   shape): update README demo with exact model tag; else record honestly.
6. CODEX VALIDATION (owner-authorized 2026-07-19): one full `-m eval -q`
   with the standard codex driver; expect the five dropped floors to
   recover + new-scenario floors to bootstrap; update ratchets SAME
   commit. Read new traces → feed loop step 1.
7. STATE.md item 11 + QUESTIONS board update (drafts:
   scratch/prompt-lab/draft_state_item11.md, draft_questions_updates.md —
   revise with actual results incl. P1 story before folding in).
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

- **P1 gemma verdict (2026-07-19 ~01:30): PASS** — plan mini 7/9 (was 2/9
  bled, 5/9 iterV baseline; now ABOVE baseline), zero letter-path
  outputs. Remaining fails are pre-existing classes: refinement-question
  15-word cap (deadline_compression), topic-padding 19>18 on
  plan_single_fact_goal (QUEUE candidate: single-fact goals padding the
  tree — smallest-path rule may need the same treatment downward
  calibration got). qwen mini IN FLIGHT → iterW2_qwen35_4b_plan.jsonl
  (if dead on resume: rerun per NEXT step 3).

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
