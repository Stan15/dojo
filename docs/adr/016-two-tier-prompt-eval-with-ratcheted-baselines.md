# ADR 016: Prompt Evaluation with Ratcheted Baselines (Three Tiers)

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

4. **Fulfiller-agnostic by construction.** The eval runner takes any fulfiller
   command string (`DOJO_EVAL_FULFILLER="<cmd>"`, same one-string contract as
   production: prompt on stdin → JSON on stdout → salvage-extract) and derives
   the baseline slug from it. Multiple fulfillers can each maintain their own
   committed baseline, and the system's model-neutrality principle (blueprint
   §9.3) is *itself* testable by running the same corpus across capability
   tiers. `codex exec` is simply the first locally available fulfiller — never
   assumed, never special-cased. Evals skip with an honest count when no
   fulfiller is configured; they never silently pass.

5. **Reproducibility, honestly bounded.** The scenario corpus and scoring are
   fully deterministic; model sampling is not. Mitigations: scores aggregate
   over `DOJO_EVAL_SAMPLES` runs (default 1, raise for stability), the ratchet
   compares against the baseline with the baseline's recorded sample count, and
   scorecards record the command string + date so drift in the external model
   is diagnosable rather than mysterious.

## Tier 3 — judged pedagogical quality (owner requirement, 2026-07-07)

Compliance says the output is *usable*; Tier 3 asks whether it is *good
pedagogy* — and whether the system demonstrably learns from the learner's
signals. An LLM judge is inherently noisy, so every design choice below exists
to buy reliability:

1. **Binary rubric criteria, never scales.** Each scenario carries a
   hand-crafted `judge_rubric`: yes/no questions with weights ("Does at least
   one exercise directly target the seeded aux-choice misconception?", "Are the
   three exercises distinct sub-skills, not rephrasings?", "Given 0.3 recent
   accuracy, is every item single-step?"). Binary votes aggregate reliably;
   1–10 scores do not. Scenario score = weighted pass fraction.

2. **Judge answers are evidence-anchored and validated.** The judge must quote
   verbatim from the judged output for every verdict; quotes are checked as
   substrings mechanically (the same trick that disciplines grading). A verdict
   without real evidence is discarded as a judge failure, not counted.

3. **Judge calibration gate.** Every scenario commits a planted **good** and
   **bad** reference output (hand-written exemplars). Before judging real
   outputs, the judge grades both references blind; if it fails to score
   good > bad, the run aborts as "judge unreliable" — noise is refused, not
   averaged in. This also detects silent drift in an external judge model.

4. **Variance is measured, then thresholded.** N driver samples × K judge votes
   per criterion (majority wins); scorecards record mean and spread per
   scenario. The ratchet flags regression only when the new mean falls below
   the baseline mean by more than the recorded spread — so a minor prompt tweak
   produces a readable verdict instead of coin-flip noise.

5. **Baselines key on the (driver, judge) pair.** Scorecards live at
   `evals/baselines/<driver-slug>__<judge-slug>.json`; comparisons are only
   ever within the same pair, so "same model + same grader = comparable" holds
   by construction.

6. **Longitudinal scenarios test the learning loop itself.** The crown-jewel
   scenarios are scripted multi-step histories: seed rich signals (recurring
   error patterns, too_easy skips, stated deadlines) → run reflect → apply →
   run generation → judge whether generation *visibly used* what reflection
   learned (targets the weakness, skips the mastered, respects the deadline
   compression). This is the pedagogical-strength flex: not "is the exercise
   nice" but "did the system adapt".

## Consequences
- Prompt iteration gets a safety net: cheap byte-level pins always; real-model
  compliance ratchets when you ask for them.
- The eval harness doubles as the integration test of the task contract itself
  (compile → fulfill → validate → apply is exactly the production path).
- Known limit, stated honestly: Tier 2 measures compliance and structure, not
  pedagogy. Semantic quality review stays human (reading `evals/reports/`), and
  an optional LLM-judge lane can be added later without changing the ratchet.
