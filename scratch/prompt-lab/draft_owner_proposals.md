# Two owner proposals (drafted 2026-07-19 during R3-LFM probe; deliver via
# QUESTIONS board when the current queue quiets — both owner-gated design
# changes, out of prompt-lab unilateral scope)

## Proposal 1 — Reflect decomposition (STATE 7d) now has closing evidence

The 7d proposal (owner called the 5-job reflect call an anti-pattern) was
drafted on intuition; the prompt-lab campaign has now ELIMINATED every other
explanation for the reflect ceiling:

- Word-cap rejections: fixed (W1) — no longer a reflect failure source.
- Questions-format lottery: fixed (W2) — was the run-churn root cause.
- Evidence decoration: fixed (W3, grade-side).
- What REMAINS at qwen3.5:4b after all three: journal-omission (6/14 fails
  in the confirmation run) and op-requirement composition (op=create
  missing evidence/text, op=update/resolve missing id — 6/14). Both are
  attention-budget failures: the model drops whole obligations when the
  task carries five at once (ops + strategy + questions + retirements +
  journal). No validator or wording fix has moved them across 6 template
  generations (P4a/P4b/P8/P9b/W1/W2 all measured).
- Cross-model corroboration: gemma3:4b (27/30) mostly survives the 5-job
  call; every sub-4B model fails it primarily on dropped obligations
  (lfm-instruct reflect 0/27!). The kind's difficulty is COMPOSITIONAL,
  exactly what decomposition addresses.

Proposal: pilot a two-call decomposition (call 1: ops+strategy with the
evidence window; call 2: journal+questions+retirements with call 1's output
in context) behind a compiler profile, measured against the single call on
the same battery set. Token cost rises (second prompt overhead ~1KB); the
density question is whether acceptance gains outweigh it — the campaign can
measure this in one cycle once approved.

## Proposal 2 — Mixed-model deployment (per-kind routing table)

The bake-off's per-kind profiles diverge more than totals:

| kind | best sub-4B cell | rate | 4B reference |
|---|---|---|---|
| plan | lfm2.5-thinking:1.2b | 11/13 | qwen 10/13, gemma 13/13 |
| diagnostic | lfm2.5-thinking:1.2b | 7/7 | 4B ≈ same |
| generate | lfm2.5-thinking:1.2b | 16/24 | gemma 21/22 |
| route | lfm2.5-instruct:1.2b | 10/13 | gemma 12/13 |
| grade | (none viable) | 12/20 granite-3GB | gemma 14/16 |
| reflect | (none viable) | 17/27 granite-3GB | gemma 20/23 |

A learner with ~1GB of memory could run plan/diagnostic on lfm-thinking and
route on lfm-instruct (same 730MB family, swap cost is load time) and only
need a bigger model (or the hosted tier) for grade/reflect. The compiler's
fulfiller-profile machinery already selects per-kind fragments; extending
the config to a per-kind MODEL table is a store-config change + CLI surface
(owner-gated: new config contract + docs). Honest caveat: model-swap
latency on ollama (~2-6s per load) makes this a daily-session pattern
(batch by kind), not an interleaved one — the task queue already groups by
kind, so the swap count per day is small.

Evidence: bakeoff_*.jsonl (7 models × 104 steps, committed), WORKBENCH
bake-off table, README small-model section (already re-based).
