# PROMPT LAB WORKBENCH — live campaign state

_Directive: docs/PROMPT_LAB.md. This file is the resumption point: a fresh
or woken session reads the directive, then this, then executes NEXT._

## Phase

BOOTSTRAP (2026-07-19, ~01:15): finishing the drop-diagnosis pipeline
before the open-ended loop starts. P1 fix APPLIED to campaign_plan.md
(words-only depth rule); its verification mini-battery is IN FLIGHT.

## IN-FLIGHT + WORKING-TREE INVENTORY (a resuming session reads this first)

- **REPLICATION BATTERY IN FLIGHT (launched 2026-07-18 ~23:52,
  workers=1, all 9 plan scenarios)** →
  scratch/token-diet/baselines/iterW2_qwen35_4b_plan_rep2.jsonl.
  WHY: merged run-1 gave qwen 3/9 ok (iterW was 5/9), ZERO letter-paths
  — below the pre-reg ≥4/9 line, but two flips (extend_not_duplicate,
  prior_expertise_scoping) are within the ±3 single-run band → pre-reg
  mandates replication before adjudicating. ADJUDICATE ON RESUME from
  run-1 (iterW2_qwen35_4b_plan.jsonl, merged+complete) + rep2 combined:
  if rep2 ≥4/9 ok and zero letter-paths → P1 qwen PASS (use rep2 or
  best-representative run for the splice; note both in ledger); if rep2
  ≤3/9 → qwen genuinely regressed 2 → weigh gemma's +2-over-baseline
  PASS vs qwen's −2: the pre-reg's revert arm (Check-line-only depth
  statement) applies unless failure transcripts show non-P1 causes;
  read the FAIL transcripts EITHER WAY (classes queued below). If rep2
  dead on resume: rerun its exact command (workers=1).
  Then: python scratch/prompt-lab/splice_iterw2.py qwen35_4b
  → resume NEXT step 4 (build_output_budget both models, full pytest,
  COMMIT 2).
- **FILL BATTERY DONE (~23:50)** — 3 rows, 0 infra, merged over the
  infra rows of iterW2_qwen35_4b_plan.jsonl (now 9 complete rows).
  Fill detail (launched 2026-07-18 ~23:47, workers=1):
  3 qwen scenarios that timed out in the 23:37 rerun →
  scratch/token-diet/baselines/iterW2_qwen35_4b_plan_fill.jsonl
  (filters: plan_goal_in_learner_language plan_extend_not_duplicate
  deadline_compression). If dead on resume with <3 rows: rerun that
  exact command (workers=1 is deliberate — 3 concurrent plan-length
  generations share the GPU 3-way and blow the 240s driver timeout;
  that's what voided the 23:37 attempt's 3 rows. Root-caused: NOT a
  template effect — completed iterW2 rows are FASTER than iterW,
  44-107s vs 121-195s, similar bytes).
  - When fill completes: merge its 3 rows over the 3 infra rows in
    iterW2_qwen35_4b_plan.jsonl (match by scenario), adjudicate P1 qwen
    (rule in ledger/pre-reg: ≥4/9 ok, zero letter-paths; current valid
    rows: 2 ok / 4 fail, ZERO letter-paths anywhere), then
    python scratch/prompt-lab/splice_iterw2.py qwen35_4b
  - gemma splice DONE: iterW2_gemma3_4b.jsonl written (79 rows, ok=67).
  - WAIT-TIME WORK QUEUED: read the 4 qwen FAIL transcripts in
    iterW2_qwen35_4b_plan.jsonl — new failure classes to diagnose:
    path-pattern violations ×2 (prior_expertise_scoping — flipped from
    iterW ok=True — and recall_skill_lanes), min_accuracy non-number
    (single_fact_goal), missing mission/name + topics-not-dict
    (unrealistic_timeline). Zero letter-paths (P1's poison absent).
  gemma3:4b mini is DONE — P1 verdict PASS, see Results ledger.
  ssh-agent leak FIXED at source (~/dotfiles/.shared_shellrc guarded;
  verified 3 shells → 1 agent reused).
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
- **Parallel doctrine LIVE (2026-07-19)**: owner directed subagent
  parallelism + resource guardianship; doctrine written into
  docs/PROMPT_LAB.md (§Parallel experimentation doctrine). Binding here.
- **RESOURCE EVENT 2026-07-18 ~23:22**: pre-spawn check found 1-min load
  135 (8 cores), swap 8.3/9.2GB, 95MB unused RAM. Cause: ~1709 leaked
  ssh-agent processes (accumulating since ~Jul 17; source not in
  ~/.zprofile — undiagnosed). pkill denied by permission classifier →
  reported to owner with one-liner (`pkill -x ssh-agent`). Battery left
  running (shape-verdict mini, not latency-critical). NO new heavy
  launches until load normalizes. Treat this machine's latency numbers
  as suspect while starved.

## Parallel slate (planned — DEFERRED until usage renews + load normal)

Per doctrine: no spawns during imminent usage outage. First slate after
renewal, if load is sane:

- **Lane C1 (cognitive): qwen3.5:0.8b rejection taxonomy** (queue item
  "sub-4B rescue arms"). Reads ONLY scratch/token-diet/baselines/
  *qwen35_08b*.jsonl (base, base2, armJ, armJ2) + src/dojo/prompts/
  README.md for failure-mode vocabulary. MUST NOT read: corpus/holdout/,
  evals/baselines/*__holdout*, evals/reports/holdout-*, visible corpus
  content beyond what the jsonl rows embed. Deliverable:
  scratch/prompt-lab/taxonomy_qwen35_08b.md — failure classes with
  counts, each mapped to a candidate mechanism + rescue-arm idea.
  Decision rule: taxonomy is input to rescue-arm pre-registration; if
  >80% of rejections are one syntactic class, a single minimal-skeleton
  arm gets designed; if diffuse, document capability-floor evidence.
  Runtime ~10-15 min. Reconcile: orchestrator reads doc, pre-registers
  arms in WORKBENCH.
- Lane C2 (cognitive, after C1 or parallel): 6i trap-scenario DRAFTS
  (~2/kind, visible-corpus additions) per directive §queue — brief to be
  written at spawn time per doctrine (needs the pre-registration first).

## NEXT (exact order)

1. DONE ~01:05 — letter-bleed fix applied to campaign_plan.md (words-only
   rule; zero abstract letter-paths beyond the skeleton's single "a.b.c").
2. DONE ~01:08 — footprint regenerated (plan 3150→3316, deliberate).
3. DONE 2026-07-19 — both minis complete (gemma 7/9 PASS; qwen rep2 4/9
   PASS per pre-reg; two VOID attempts documented in ledger — resource
   starvation, then worker-contention timeouts; workers=1 is the rule
   for plan-only minis now).
4. DONE 2026-07-19 — spliced (qwen 41/79, gemma 67/79), output-budget
   rebuilt (templates f282300548c49b80), 822 tests green, COMMIT 2 =
   d69ff5c. (gemma speed probe optional — nice-to-have only.)
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

- **P1 qwen verdict (2026-07-19 ~13:15): PASS per pre-reg.** rep2
  (all-sequential, cleanest methodology) 4/9 ok, ZERO letter-paths —
  meets the ≥4/9 + zero-letter-path bar exactly. Run-1 (merged
  contention+fill) was 3/9, also zero letter-paths; iterW baseline 5/9.
  18/18 qwen valid rows + 9/9 gemma rows show zero letter-paths: the
  P1 bleed mechanism is DEAD. rep2 used for the splice (uniformity,
  chosen per pre-reg's 'best-representative' arm; run-1 preserved as
  iterW2_qwen35_4b_plan_run1.jsonl). Non-P1 failure classes logged for
  the loop: plan_unrealistic_timeline fails IDENTICALLY both runs
  (mission/name missing, topics[0] not a dict — stable, diagnose
  transcripts); path-charset violations recurrent (deadline_compression
  both runs); depth>4 once; undeclared-topic typo once (musi.music).

- **P1 qwen mini attempt 1 (2026-07-18 23:2x): VOID (7/9 driver
  timeouts under load-135/swap-full machine — see resource event).**
  The 2 valid rows, weak-signal only, n=2: plan_extend_not_duplicate
  ok at 4B AGAIN (now n=2 for the depth-statement fix, still
  encouraging-only); deadline_compression failed on a DIFFERENT
  pre-existing class — hyphens in topic paths
  (multi-stage-builds vs ^[a-z0-9_]+ pattern; QUEUE candidate:
  path-charset statement in plan template? verify frequency first).
  ZERO letter-path outputs in both rows (consistent with P1, not
  sufficient). Verdict awaits the valid rerun.

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
