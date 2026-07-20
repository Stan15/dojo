# REFLECT-DECOMP PILOT — design + pre-registration (owner-approved 2026-07-20)

## Split (from the approved proposal, refined)

- **Call 1 — reflect.ops**: RULES 1-3 + 5 (insights adjudication, strategy,
  plan revision, retirements) + ALL evidence sections (MISSION/STRATEGY/
  PLAN/INSIGHTS/TRENDS/ATTEMPTS/FEEDBACK). Output: {insight_updates,
  strategy, plan_revision, topic_retirements}. Retirements stay here —
  they need TRENDS evidence.
- **Call 2 — reflect.voice**: the two most-dropped obligations (journal,
  questions) with a COMPACT digest of call 1's applied output (ops
  summary lines + dials moved) + FEEDBACK + rule 4 + rules 6-7. Output:
  {questions, journal}. The model writes the narrative AFTER the
  decisions exist — the compositional-load thesis says this is where the
  dropped obligations get their own attention budget.

## Implementation shape (opt-in, measurement-first)

- Compiler: compile_reflect_ops / compile_reflect_voice behind
  fulfiller.reflect_mode = "single" (default, byte-identical) | "split".
  Templates: campaign_reflect_ops.md + campaign_reflect_voice.md built
  from the existing template's sections (FINDINGS.md wins carried:
  orthogonal examples, create-suppression, neutral anchor, cap anchors).
- Schemas: ReflectOpsResult (no journal/questions), ReflectVoiceResult
  (journal + questions only; W2 coercion + W1 walls apply). Merge =
  full ReflectResult → existing apply path unchanged (contract preserved:
  ONE apply, two generations).
- Pilot harness: scratch/prompt-lab/decomp_probe.py drives both calls
  per scenario, merges, submits via service; records per-call bytes/secs
  + merged outcome. Product wiring (drain_tasks two-step) is NOT in the
  pilot — measurement only, per the approval.

## Pre-registration (bars set BEFORE any run)

Baselines (current-arm fulls + newest minis): qwen reflect 14/27;
gemma 27-28/30. Residual classes: journal-omission (~3-6/run qwen),
op-requirement composition (~6/run qwen).

- PRIMARY: qwen split-mode merged acceptance ≥ 18/27 (+4 cells minimum)
  AND journal-omission ≤ 1 AND op-composition fails do not rise.
- GUARD: gemma split ≥ 26/30 (flat-or-better); no new failure class.
- TOKEN BAR (density): added whole-trace cost ≤ +45% per scenario
  (call-2 prompt is compact: digest + 2 rules + skeleton ≈ 1.2KB
  prefill + short decode). Density verdict at adjudication: each
  converted rejection saves a full single-call regeneration (~2.5KB
  decode + retry prefill) — the pilot wins if saved regenerations ≥
  added second-call cost at the measured acceptance delta.
- Sub-4B ride-along (no bar): lfm-instruct split reflect — its 0/27
  single-call reflect is the mixed-model proposal's missing cell; any
  nonzero result is signal.
- REVERT rule: any bar missed → profile stays in tree (opt-in, unused,
  default byte-identical — RSIMP precedent) but the pilot verdict is
  NEGATIVE and the proposal closes with receipts.

## Sequencing

Implement ONLY after the in-flight codex validation adjudicates (quiet
tree). Then: schemas+compiler+templates+tests (default byte-identity
test mandatory) → full pytest → COMMIT INFRA → batteries (gemma, qwen,
lfm-instruct; serial, chained) → adjudicate → verdict commit. Holdout
relay (aggregate-only) happens after codex greens and BEFORE decomp
batteries touch anything — the gate measures the committed 9-arm state.
