# ADR 016: Two-Tier Prompt Evaluation with Ratcheted Baselines

## Status
Accepted (2026-07-07). Product-owner requirement: "benchmark our harness system on
different data … a baseline to prevent regress when tweaking the prompts … part of
our testing suite."

## Context
Prompt templates are product surface: an edit can silently degrade what every
model produces. But real-model calls are slow, non-deterministic, and cost money —
they cannot run on every CI invocation. The regression system must be part of the
test suite without making the test suite flaky.

## Decision
Two tiers, both in `pytest`, split by what they need to run:

1. **Tier 1 — deterministic, every run.** Golden fixtures pin the *inputs*:
   rendered templates and fully compiled task payloads for fixed store states
   must match byte-for-byte and stay within the §2 byte budgets
   (design/prompts.md). Any prompt edit forces a reviewed fixture diff in the
   same commit. Zero model involvement. (Lives in `tests/test_prompts.py` and
   the compiler tests.)

2. **Tier 2 — real-model evals, on demand (`pytest -m eval`).** A scenario corpus
   (`evals/scenarios/`: seeded store state + task kind + expectations) is
   compiled, sent through a configured fulfiller command, and the responses are
   scored **deterministically** — by the same validators the appliers use (JSON
   shape, exact counts, score bands, word caps, evidence-substring,
   route-target-exists) plus structural quality heuristics (answer not leaked
   into prompt text, rubric present, self-containment lexical checks).
   No LLM judge in v1: *mechanical compliance rate is the very thing our
   prompt-craft rules target*, so it is the right primary metric, and it is
   reproducible.

3. **Ratcheted baselines.** Each eval run writes a scorecard
   (`evals/baselines/<model-slug>.json`: per-scenario compliance + quality
   scores). Committed baselines are the floor: a run scoring below its model's
   baseline fails the eval suite (method §8, ratchet progress). Improvements
   update the baseline in the same commit as the prompt change that earned them.
   Baselines are per-model — scores are only comparable within a model.

4. **Reference fulfiller: `codex exec`** (available on the owner's machine),
   driven through the same one-string fulfiller contract as production
   (`prompt on stdin → JSON on stdout → salvage-extract`). Skipped automatically
   when the command is unavailable (honest skip count, never a silent pass).

## Consequences
- Prompt iteration gets a safety net: cheap byte-level pins always; real-model
  compliance ratchets when you ask for them.
- The eval harness doubles as the integration test of the task contract itself
  (compile → fulfill → validate → apply is exactly the production path).
- Known limit, stated honestly: Tier 2 measures compliance and structure, not
  pedagogy. Semantic quality review stays human (reading `evals/reports/`), and
  an optional LLM-judge lane can be added later without changing the ratchet.
