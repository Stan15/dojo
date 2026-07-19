# PROMPT LAB WORKBENCH — live campaign state

_Directive: docs/PROMPT_LAB.md. This file is the resumption point: a fresh
or woken session reads the directive, then this, then executes NEXT._

## Phase

STEPS 5+6 IN FLIGHT (2026-07-19 ~01:22): COMMIT 2 (d69ff5c) and
COMMIT 3 (fb9fe04) landed; P1 adjudicated PASS both models. Two lanes
running in parallel per doctrine:
- LOCAL lane: README demo retry, qwen3.5:4b --no-think, ≤2 budgets
  (task b21bw9vtx). Then gemma3:4b same command if qwen doesn't land a
  GOOD reflect. If dead on resume: rerun
  python scratch/prompt-lab/readme_demo_retry.py "python scratch/token-diet/api_driver.py qwen3.5:4b --no-think" 2
- REMOTE lane DONE (~01:50, 45min run): codex validation 73/84.
  **ALL FIVE target drops RECOVERED** (none in the fail list) and the
  three unmoved weak floors moved off the list too. **11 OTHER floors
  fell** (margin 0.1): chain_strategy_change_then_calibrated_generation,
  deadline_compression, diagnostic_mission_anchoring,
  math_scaffolded_generation, plan_recall_skill_lanes,
  plan_single_fact_goal, plateau_remediation, pure_recall_grounded,
  reflect_learner_contradicts_evidence, route_new_leaf_when_warranted,
  too_hard_scaffolding_response (0.57, c1 'scaffolding medium not
  high'). 5/11 are generate+scaffolding — prime suspect: the new
  calibration_* fragment selection. NO ratchet updates from this run
  (floors only move on wins). ADJUDICATION PROTOCOL (in order, free
  first): (1) per failing scenario, diff compiled payload NOW vs
  d69ff5c^ — unchanged payload ⇒ variance candidate, changed ⇒
  regression candidate; (2) read report traces for changed ones
  (evals/reports/, newest quality-*.json — VISIBLE report, allowed);
  (3) targeted codex re-run of only the failing subset for the
  variance candidates (multi-sample rule: a floor drop needs BOTH
  samples failing). Report file: check ls -t evals/reports/.
- Wait-time work (this session, during lanes): qwen FAIL-transcript
  diagnosis; STATE item 11 draft revision.

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

## ADJUDICATION RESULT (~04:15): 7/11 recovered, 3 real mechanisms remain

Run 20260719-064412 (targeted, 11 scenarios): P5 CONFIRMED (topic
counts recovered; deadline_compression now fails only c5 recall/skill
mix at 0.89 vs 0.90 — margin noise, different criterion, no action).
P4a CONFIRMED (plateau single-insight). P4b PARTIAL (too_hard
recovered; plateau 0.12→0.5 — right lever, wrong level: scaffolding
medium not high; the confined-raise line states no level). All five
replicate-only scenarios PASSED — variance confirmed, floors intact,
zero ratchet changes. Two-sample REAL: plateau level (P4b2),
learner-contradicts mismatch branch (P8), math scaffold answer-leak
(P7).

## NEXT BATCH pre-registrations (applied → battery cycle → COMMIT 5)

- **P2** (charset, pre-reg above) — plan.
- **P6** skeleton phases literal ["a.b"] → ["a.b.c"] to match the
  topics literal (two-sample gemma bait; the skeleton currently
  demonstrates the violation its Check line forbids) — plan.
- **P4b2** state the level wherever scaffolding is the lever for
  persistent struggle: the topic-confined raise line and plateau line
  both say set it HIGH (partial support against a standing wall is
  another lap of the wall). Decision rule: plateau_remediation ≥0.9 on
  next targeted run; too_hard stays passing; local reflect minis
  same-or-better — reflect.
- **P8** mismatch branch in the rule-2 case list, before the otherwise-
  lower case: learner's stated experience contradicts the window's
  evidence → hold BOTH dials, name the mismatch (insight or rule-4
  question) — acting on contested evidence miscalibrates. Decision
  rule: learner_contradicts ≥0.9; mixed_signals + voiced-scope
  scenarios stay passing (opposite-branch controls) — reflect.
- **P7** generate: scaffolding shows the METHOD (pattern, first step,
  structure), never the completed answer value for what the item asks
  (pedagogy-foundation: no leaked clues). Decision rule:
  math_scaffolded c3 recovers; scaffolded/calibration scenarios
  (too_hard chain, downward_calibration) stay passing; generate minis
  both models same-or-better — generate.
EDITS APPLIED ~04:30 (uncommitted, COMMIT 5 held by output-budget
gate): P2+P6 in campaign_plan.md, P4b2+P8 in campaign_reflect.md, P7
in exercise_generate.md. Free gates green; generate golden regenerated
(2-line diff); footprint updated (generate +91B, plan +108B, reflect
+349B — deliberate, priced against 0.5/0.67 two-sample defects).
iterY BATTERY CYCLE (ONE at a time; same 23 reflect stems as iterX;
plan filters "plan_ deadline_compression vague_goal" workers=1;
generate stems = kind exercise.generate rows of iterX ~20 stems):
1. DONE ~04:55 — REGRESSION SIGNAL: qwen reflect 8/23 vs iterX 11/23
   (−3, edge of band, wrong direction). journal-missing DOUBLED 3→6,
   questions errors 2→5: the +349B rule mass crowds tail fields at 4B.
   Plateau + pending_grade + restructure_minimal newly PASS (P4b2
   works at 4B too) — the cost is the verbosity, not the semantics.
   DECISION (recorded ~05:00): after the plan battery lands, TIGHTEN
   the additions ~−200B — (a) delete the redundant lever sentence
   ("When scaffolding is the lever... wall." — each case already
   states high inline); (b) compress the mismatch case to "FEEDBACK
   contradicts the window's evidence → hold both dials, name the
   mismatch (insight or question);". Then RERUN qwen reflect
   (iterY2_qwen35_4b_reflect.jsonl). Adjudicate: ≥11/23 → proceed to
   remaining batteries under tightened wording (gemma reflect measures
   tightened too); ≤9/23 → the case-list structure itself is the 4B
   cost → revert reflect to the iterX wording + plateau-only, keep
   P8 mismatch as a codex-profile question for the owner (fulfiller
   profiles are the doctrine's answer to per-class divergence).
   NO reflect edit until the in-flight PLAN battery notification
   (quiet-tree letter rail; plan compiles don't read reflect, but the
   rail holds by letter).
2. DONE ~05:15: qwen plan 5/9 (iterX 4/9, same-or-better), ZERO
   letter-paths, charset fails 4→1, a.b bait GONE — P2+P6 PASS at
   qwen. Remaining fails are content-level (typo'd undeclared refs,
   one charset, unrealistic_timeline structural).
2b. TIGHTENING APPLIED ~05:17 (reflect 7446→7233B, −213; free gates
   green; footprint updated): lever sentence deleted, mismatch case
   compressed to "FEEDBACK contradicts the window's evidence → hold
   both dials, name the mismatch (insight or question)". IN FLIGHT:
   iterY2 qwen reflect rerun (task bk0yvhydi, ~05:18) →
   iterY2_qwen35_4b_reflect.jsonl. Adjudicate per item-1 decision:
   ≥11/23 proceed (gemma reflect measures THIS wording; reflect
   splices use iterY2 files); ≤9/23 revert to iterX reflect wording +
   plateau-only, P8 becomes an owner question (codex-profile).
   BOOKKEEPING: plan batteries (iterY) remain valid — plan template
   untouched by the tightening; generate batteries still owed (P7
   tree unchanged since edit).
2c. ADJUDICATED ~05:45: iterY2 qwen reflect 13/23 (> iterX 11/23),
   journal-missing 6→2, plateau AND contradicts PASS at 4B. Tightened
   wording ADOPTED; reflect splice uses iterY2 file.
3. DONE ~06:10: qwen generate 16/20, 0 infra (iterX 14/15 + 5 infra —
   denominators differ; 2 of 4 'newly failing' were iterX infra rows).
   Real flips: 2 down (chain_strategy escape-hatch empty-items,
   verbatim_poetry skill-field omission — pre-existing classes, no P7
   mechanism), 1 up (downward_calibration). math_scaffolded (P7
   target) stays ok. VERDICT: within-band churn, PROCEED.
4. DONE ~06:40: gemma reflect 19/23 (iterX 20/23, within band);
   plateau AND contradicts PASS at gemma too. All 3 distinctive fails
   are one class: verbatim copy of the default fragment's DESCRIPTIVE
   placeholder value "the insight's id" → QUEUE P9: replace with a
   realistic literal id (craft rule 7: realistic values only; this
   value predates the campaign — worth its own mini when batched with
   the next reflect edit).
5. DONE ~07:05: gemma plan 7/9 (rep2 8/9, within band), ZERO
   letter-paths, a.b bait GONE (single_fact fails only the
   refinement-question 15-word cap now — pre-existing class). P6
   verified both models; P2 residual 1 charset fail at gemma.
6. DONE ~07:30: gemma generate 18/20 (iterX 16/20, UP 2; churn 1↓3↑).
   CYCLE COMPLETE — all six batteries same-or-better or within band.
   Spliced (qwen 47/79 ok — up from iterX 42; gemma 68/79 flat),
   output-budget rebuilt (templates 6c09eab1dfdc0404), 825 green,
   **COMMIT 5 = 1ff6425**.
7. ADJUDICATED ~07:50 (run beg51o8y1): 8/9 pass — plateau_remediation,
   reflect_learner_contradicts_evidence, math_scaffolded_generation
   ALL RECOVERED at codex (P4b2/P8/P7 confirmed); controls held.
   deadline_compression 0.89 vs 0.90: c5 'all topics marked skill' —
   2nd consecutive sample → two-sample real → **P10 queued** (next
   batch with P9): principle 'compress by cutting topic count, never
   by flattening kinds — material that must be memorized stays
   recall' (~70B, plan fires once/campaign). No floors moved, no
   ratchet commit needed. DROP-DIAGNOSIS ARC CLOSED: of the 11
   codex drops — 7 fixed+verified, 4 variance-confirmed with
   controls holding; residuals are P9 + P10 (queued, evidence-backed).
7b. CODEX ADJUDICATION former entry (task beg51o8y1): targets
   plateau_remediation, reflect_learner_contradicts_evidence,
   math_scaffolded_generation; controls too_hard, mixed_signals,
   deadline_compression, single_fact_goal, downward_calibration,
   chain_strategy. Decision rules per P4b2/P8/P7 pre-regs: targets
   ≥ floor−0.1; every control stays passing. Ratchets only on wins,
   same commit. On a control regression: trace-diagnose before any
   further edit; floors never lowered.
   Splice bookkeeping: qwen = iterY2 reflect + iterY plan + iterY
   generate over iterX; gemma = all iterY-named files (measured on
   final tree). Extend splice to 3 kinds.
Adjudicate each vs iterX same-kind (same-or-better ok, zero
letter-paths for plan — P6 should REMOVE the a.b bait: single_fact
undeclared-ref must disappear; charset fails should drop under P2).
Then: splice (extend splice script to generate kind or inline),
build_output_budget (iterY), full pytest → COMMIT 5 → targeted codex
(plateau_remediation, reflect_learner_contradicts_evidence,
math_scaffolded_generation + controls: too_hard_scaffolding_response,
reflect_mixed_signals, deadline_compression, plan_single_fact_goal,
generate_downward_calibration, chain_strategy).

## CODEX ADJUDICATION former section (task b3c8culp3 — DONE, see above)

COMMIT 4 = 9fb94e8 (P4a/P4b/P5 landed; local gates in the message).
Targeted codex re-run of the 11 dropped floors running. On completion:
- P4a/P4b recovered if plateau_remediation, too_hard_scaffolding_
  response, reflect_learner_contradicts_evidence pass (and the run's
  mixed_signals/mastery controls were already green in the full run).
- P5 recovered if deadline_compression, plan_recall_skill_lanes,
  plan_single_fact_goal pass topic-count criteria (single_fact may
  still fail on the P6 skeleton bait — adjudicate the CRITERION, read
  the verdict detail, not just pass/fail).
- Replicate-only five (route_new_leaf, chain_strategy, math_scaffolded,
  pure_recall, diagnostic_mission_anchoring): second sample — pass ⇒
  variance confirmed, no action; fail ⇒ two-sample real, pre-register
  per notes (diagnostic boundary-words fix drafted in triage entry).
- Ratchet updates ONLY for recovered floors, SAME commit as any
  baseline change. If rerun fails floors again, floors STAY; iterate.
NEXT BATCH after adjudication: P2 (path-charset statement) + P6
(skeleton phases literal a.b → a.b.c, matching the topics literal —
fixes the demonstrated-violation bait; stable two-sample evidence).
Both are plan-template edits: one battery cycle (plan minis both
models, workers=1) + free gates + footprint/output-budget same commit.

## BATTERY QUEUE (P4a/P4b/P5 verification — COMMIT 4 held by
## output-budget hash gate; templates edited, free gates green) — DONE, see above

Fixes APPLIED to tree (uncommitted): reflect_ops_no_insights → ONE
create (P4a); campaign_reflect rule 2 → ordered case list, trend
before level, plateau branch (P4b); campaign_plan Check line →
'ability, not coverage' restored (P5). Batteries ONE at a time:
1. DONE ~02:45: qwen reflect 11/23 ok vs 10/21 old (rate holds, 0
   infra); churn is pre-existing classes (reason-missing, dotted-key,
   placeholder-id); journal-missing 3 vs 2-3 old (no new class).
   LOCAL GATE PASS for P4a/P4b on qwen.
2. DONE ~03:05: qwen plan 4/9 ok (= rep2 level, same-or-better), zero
   letter-paths, 0 infra. plan_unrealistic_timeline PASSES for the
   first time in 3 runs (P3 syntax-degradation case, n=1). Remaining
   fails: 4× P2 charset class + 1 structural — P2 stays queued for the
   NEXT template batch (tree frozen until COMMIT 4).
3. DONE ~03:35: gemma reflect 20/23 vs 20/23 old — identical rate,
   churn 1↔1 (legitimate_restructure ↔ resolution_amid_active_
   struggle). LOCAL GATE PASS for P4a/P4b on gemma.
4. RUN 1 ~03:50: gemma plan 6/9 (old 7/9) with ONE letter-path
   (plan_single_fact_goal phase ref 'a.b' — skeleton-literal bleed,
   P1 class; other fails: P2 charset ×1, topics 19>18 padding ×1 same
   as old). BELOW the pre-reg bar → REPLICATE launched (~03:52,
   iterX_gemma3_4b_plan_rep2.jsonl, workers=1). Adjudication on rep2:
   ≥7/9 with zero letter-paths → P5 gemma PASS (use rep2 for splice;
   run-1 noted as single-sample churn — P5's two-word edit has no
   mechanism for a.b bleed); ≤6/9 or any letter-path again → treat as
   REAL: revert P5? No — P5 is implausible as cause; investigate the
   skeleton phases example ("a.b" literal) as the standing bleed
   source and pre-register a fix (e.g. realistic phase-topic literal
   matching the topics example), separate from P5's fate.
   THEN: splice both models (splice_iterx.py), build_output_budget
   with iterX files, full pytest, COMMIT 4, targeted codex re-run.
5. Splice per kind over iterW2_<model>.jsonl → iterX_<model>.jsonl
   (extend splice_iterw2.py or inline: drop kind rows, append mini),
   build_output_budget with both iterX files, footprint already
   updated, full pytest → COMMIT 4.
6. Targeted codex re-run: the 11 failing scenarios + route_new_leaf
   (variance replicate) — decision rules in each pre-reg. Ratchets
   only on wins, same commit.
Decision rules bind per pre-reg P4a/P4b/P5: local minis same-or-better
ok-rates vs iterW2 per kind; zero letter-paths; recovered codex floors
without losing mixed_signals/mastery_resolution/extend_not_duplicate.

## 6i SUB-ARC CLOSED (~13:40) — commits e4a3aa7 f88df7e 6cfdb7c 36ac04b

Corpus 92 (deliberation:12), opt-in anchor profile shipped+measured
(caliber-divergent verdict in QUESTIONS 6i), 9 trap floors
bootstrapped. NEW WEAK CELLS from the traps (next loop iterations, in
leverage order):
1. **plan celestial trap: codex 0.0** — dependency root cut under
   deadline even at strong tier (sourdough 0.4 same class). Diagnose
   the trace (report 20260719-085715); candidate P11: plan template
   states WHICH topics survive compression (never cut what other
   topics depend on — cut breadth, keep roots) — verify scenario
   fairness in the trace FIRST (rubric could be miswitten; T2-authored).
2. **gen_collision compliance: codex 4-items-for-3** — collision
   pressure over-generates even at codex. Read driver_trace; candidate:
   generate template states the item budget binds even under
   competing insights (compose, don't append). Scenario fairness check
   first (n_items=3 with 3 colliding constraints may be UNDER-specified).
3. diag_implied_axis_italian_oral 0.6 — read verdicts.
Then standing queue: P9b (compiler-interpolated real insight id),
retry-error pedagogy, example-bleed hardening, judged spot-sets per
adopted arm.

## 6i SUB-ARC (started ~10:00) — trap-benchmark + anchor profiles

Design source: QUESTIONS 6i (owner-approved; codex cell authorized by
the directive §queue). PARALLEL SLATE (doctrine-compliant lane rows):

- **Lane T1 (cognitive, subagent): grade+reflect traps.** 2 scenarios
  each: grade right-result-broken-method; reflect aggregate-vs-
  latency×topic-decomposition + distractor. MAY read:
  src/dojo/evals/corpus/quality/route_url_bleed_near_empty_registry.yaml
  (format), src/dojo/schemas.py, src/dojo/limits.py, the two relevant
  templates. MUST NOT read/open: corpus/holdout/**, evals/baselines/
  *__holdout*, evals/reports/holdout-*, other visible corpus files,
  scratch/prompt-lab/WORKBENCH.md. Deliverable: 4 YAML drafts to
  scratch/prompt-lab/traps/, filenames+one-line summaries reported.
  Reconcile: orchestrator reviews content, moves to corpus, ratchets
  floors. Runtime ~15 min. Restart: re-spawn from this row.
- **Lane T2 (cognitive, subagent): plan+route traps.** plan:
  deadline-forces-cutting-dependency-root; route: lexical-match
  campaign vs semantic owner. Same reads/exclusions (their templates),
  same deliverable shape.
- **Lane T3 (cognitive, subagent): generate+diagnostic traps.**
  generate: insight-collision engineering; diagnostic: jointly-implied
  open axis. Same reads/exclusions, same deliverable shape.
- **Orchestrator (this session, parallel): anchor-profile plumbing** —
  compiler-selected invitation fragment (exact 6i wording), opt-in
  fulfiller profile config, free tests. Then review lanes → corpus
  commit with 'deliberation' category floors → A/B battery plan
  (2 replicates per cell, ONE battery at a time).
Decision rules: pre-registered in QUESTIONS 6i verbatim (adopt
invitation as opt-in profile ONLY if trap-avoidance rises materially
at some caliber, neutral floors regress nowhere, bytes/latency hold).

PROGRESS (~11:10): T1/T2/T3 lanes delivered 12/12; orchestrator
review fixed 4 step blocks (grade attempt_id shape, gen difficulty
kwarg); all 12 verified through seed→compile; corpus commit e4a3aa7
(floors 92, category deliberation:12, footprint diagnostic
representative 1694→1991 corpus-order). Plumbing commit f88df7e
(fulfiller.anchor_profile, default byte-identical). measure.py gained
DOJO_ANCHOR_PROFILE env arm switch (uncommitted — rides with the A/B
results commit).

**6i VERDICT (~13:05, all 8 cells, 2 reps/cell): ADOPT AS OPT-IN with
per-caliber guidance.** qwen3.5:4b takes the invitation (pre_bytes
0→~450) and trap-avoidance rises 44%→75% of measurable rows (avoided
4→6, hit 3→1, rejects flat 12→13) — consistent both reps. gemma3:4b
IGNORES it (pre_bytes 8→8, no written deliberation), avoided 15→12,
rejects 2→4: mildly harmful, mechanism never engages. Pre-reg bar met
at the qwen caliber; neutral default untouched (byte-identical).
Guidance: profile for qwen-class visible thinkers only; never
gemma-class. Codex B cell SKIPPED deliberately (pre-reg expected flat
= low information; spend discipline — authorization is not
obligation; owner may request it anytime). Judged floors for the 12
traps bootstrap via the arm-A codex run (launching). Data:
trapAB_{qwen,gemma}_{A,B}_{r1,r2}.jsonl + trap_check.py.

A/B GRID (12 traps; filters: diag_implied_axis gen_collision
grade_canceling grade_memorized plan_deadline_cuts reflect_fast_wrong
reflect_topic_split route_lexical; workers=2; ONE battery at a time):
- Cell 1 IN FLIGHT: qwen A r1 → trapAB_qwen_A_r1.jsonl (task
  b02ad5tli ~11:12). Then: qwen B r1 (DOJO_ANCHOR_PROFILE=deliberate),
  qwen A r2, qwen B r2, gemma A r1, gemma B r1, gemma A r2, gemma B r2.
- Trap-avoidance measured DETERMINISTICALLY per scenario (the traps'
  wrong answers are field-detectable: grade score 1.0-vs-0.3, reflect
  difficulty lowered-vs-held, route campaign choice, plan root-topic
  survival) — scratch/prompt-lab/trap_check.py (being written).
  B−A per caliber = restriction effect; pre_bytes confirms mechanism.
  Codex spot cell (judged) AFTER local grid, spend-batched once.

## ARC CLOSED ~09:40: iterZ done, COMMIT 6 = 04368ad, P10 CONFIRMED

Targeted codex 6/6: deadline_compression RECOVERED (c5 kind-mix
fixed), all controls hold. EVERY scenario from the original 11-drop
codex fail list is now recovered-and-verified or variance-confirmed
with floors intact. No floors moved this run. Next: experiment queue
item 1 — 6i deliberation trap-benchmark (owner-approved design,
directive §queue): ~2 trap scenarios per kind (visible corpus
additions, coverage floors ratcheted), neutral vs strongest-elicitor
anchor profiles, B−A per caliber = restriction effect; codex cell
authorized; adopt anchor-profile only as opt-in on measured win.
Open queue behind it: P9b (compiler-interpolated real insight id),
retry-error pedagogy, example-bleed hardening, judged spot-sets.

## iterZ BATCH former header (P9+P10; COMMIT 6 landed)

EDITS APPLIED ~08:15: P9 reflect_ops_default placeholder →
realistic literal ins_4c21a9e7_0; P10 plan rule 4 'compress by cutting
topic COUNT — never by flattening kinds; memorized material stays
recall'. Free gates + footprint update ran in task bg8c4ngue (check
its head for deltas). Batteries (ONE at a time):
1. DONE: qwen reflect 10/23 (iterY2 13/23; series 11/8/13/10 — within
   ±3 band, 13 was the high outlier; accepted).
2. DONE: qwen plan 6/9 (iterY 5/9), zero letter-paths, charset class
   FULLY GONE at qwen. PASS.
3. DONE ~09:05: gemma reflect 17/23 (iterY 19/23, within band, no new
   class). P9 verdict: MARGINAL-NEUTRAL — id-copying persists (2 vs 3;
   one fail copies the NEW literal ins_4c21a9e7_0 verbatim, one
   invents ins_glaze_*). Kept (craft-rule-compliant), but **QUEUE
   P9b**: ops_example should interpolate a REAL active-insight id via
   compiler ({{ first_insight_id }}) so the example demonstrates a
   VALID op — craft rule 5, branching in compiler. 
4. IN FLIGHT: gemma plan (w1, task bsoffq8k4, ~09:07) →
   iterZ_gemma3_4b_plan.jsonl (vs iterY 7/9)
Then splice (reflect+plan over iterY files), output-budget, pytest →
COMMIT 6 → targeted codex: deadline_compression (P10 target, c5
kind-mix) + controls plan_recall_skill_lanes, plan_single_fact_goal,
mastery_resolution, reflect_learner_language, reflect_pending_grade_
integrity. Ratchets on wins same commit. AFTER: experiment queue item
1 (6i deliberation trap-benchmark — owner-approved design in
directive §queue).

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

- **P4a ops-example COUNT/TYPE anchoring (2026-07-19 ~02:10; evidence:
  codex plateau_remediation 0.12 'two insights not one' + README-demo
  qwen 2 creates in 2/2 budgets).** d69ff5c changed the reflect ops
  example from update+create (mixed types) to create+create in BOTH
  fragments → models imitate op count and type (mode 9 extended to
  COUNT). Fix: reflect_ops_default shows update+create (old shape,
  one of each); reflect_ops_no_insights shows ONE create (create is
  the only valid op there — the section line already says so).
  Decision rule: plateau c1 class recovers (exactly-one-insight
  scenarios stop double-creating) at codex on the targeted re-run;
  README-demo rerun produces 1-2 evidence-driven creates (not
  always-2); mixed_signals + mastery_resolution (multi-insight
  scenarios) STAY passing; local reflect minis same-or-better ok.
- **P4b dial-precedence hedge (2026-07-19 ~02:10; evidence: plateau
  'lowered difficulty because accuracy was 0.43' echoing the rule-2
  threshold verbatim; too_hard scaffolding medium-not-high;
  learner_contradicts difficulty-lowered-unresolved).** The d69ff5c
  global-dials/window hedges made the accuracy<0.50 threshold the
  first-matching rule for ALL sub-0.5 windows; no plateau branch
  exists (old codex inferred it; hedged codex doesn't). Candidate fix
  (VERIFY against docs/pedagogy-foundation.md BEFORE wording — anti
  reward-hack: principle must be category-wide, not rubric-phrased):
  state trend-before-level precedence — flat accuracy across the
  window with no distress markers = support gap → scaffolding raise
  (to high), difficulty held; floundering (distress markers) keeps
  both-dials; rushing carve-out untouched. Decision rule: plateau +
  too_hard + learner_contradicts recover ≥ floor−0.1 at codex;
  mixed_signals (hold-dials control) AND reflect_mixed_signals class
  stay passing; local reflect minis same-or-better.
- **P5 restore 'not coverage' scope anchor (2026-07-19 ~02:10;
  evidence: deadline_compression 15 topics >10, recall_skill_lanes 9
  topics, single_fact_goal 4 topics >1-3 at codex; gemma mini
  topic-padding 19>18).** d69ff5c's Check-line compression deleted
  'not coverage' from 'mission states ability, not coverage' — the
  scope-restraint anchor. Fix: restore the two words (+13B). Decision
  rule: the three plan scenarios' topic-count criteria recover at
  codex; plan_extend_not_duplicate (depth) stays passing; local plan
  minis (workers=1) same-or-better with zero letter-paths.
- **Variance-only (NO fix, replicate-only): route_new_leaf_when_
  warranted** — payload byte-identical to pre-iteration; single-run
  fail c4 (reason wording). Multi-sample rule: include in the targeted
  codex re-run; floor action only if it fails twice.
- **Triage complete (2026-07-19 ~02:35) — REPLICATE-ONLY set (no fix;
  floor action only on a second failure): route_new_leaf (payload
  unchanged), chain_strategy (judge PARAPHRASED 'nitrogen'→'nutrient';
  evidence gate CORRECTLY discarded — verified by rerunning
  evidence_matches; gate stays untouched, anti-reward-hack),
  math_scaffolded_generation (c3 answer-leak in one item),
  pure_recall_grounded (c3 content detail), diagnostic_mission_
  anchoring (mechanism plausible: d69ff5c 'narrower/rephrased is
  still a re-ask' hardening — whose target respects_known_insights
  RECOVERED — may inhibit mentioning the stated deadline; if it fails
  the replicate, apply boundary words: anchoring readiness against a
  stated deadline is probing, not re-asking).**

- **P2 path-charset invisible floor (2026-07-19 ~01:35, transcripts:
  deadline_compression both runs + single-fact class).** Finding: the
  plan validator enforces ^[a-z0-9_]+(\.[a-z0-9_]+)*$ but
  campaign_plan.md states only "dot-separated" + "lowercase English" —
  hyphens are never excluded. Jargon-heavy domains (CKAD: api-server)
  anchor hyphenated paths → charset rejection. Classic invisible-floor
  class (STATE item 4 rule: every validator a payload can trip must be
  stated). Hypothesis: stating "segments join words with underscores —
  no hyphens, spaces, or slashes" in WORDS (P1 lesson: zero new
  letter-path literals) removes the charset failures without moving
  anything else. Decision rule: deadline_compression's charset error
  disappears across a plan mini (both 4B models, workers=1); no new
  failure class appears; footprint delta ≤ +80B. EDIT ONLY after the
  codex lane completes (quiet tree) and after re-reading prompts
  README + design/prompts.md (hard rule).
- **P3 syntax-degradation-on-deep-paths (observation, needs mechanism
  work before pre-reg).** plan_unrealistic_timeline (fails both runs,
  iterW too): mission/name PRESENT in raw but JSON syntax corrupts
  around over-deep crammed paths (7 levels, e.g.
  katakana...days.moon.sun_mon; '"." for ","' + stray braces) → span
  recovery grabs an inner object → validator reports "mission: Field
  required" — a RETRY-PEDAGOGY bug (message teaches the wrong fix) on
  top of an over-scoping bug (unrealistic timeline → cram). Related
  queue item: retry-error pedagogy. Do NOT treat as missing-fields.


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
