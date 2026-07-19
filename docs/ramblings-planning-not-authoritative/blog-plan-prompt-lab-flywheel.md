# Content plan — "The Guardrails Are the Product: a self-improving prompt lab that can't lie to you"

_Slated 2026-07-19 (owner request). Sketch, not authoritative. Blog post
first; YouTube adaptation notes at the bottom. Everything cited here is
in git history / WORKBENCH / INSIGHTS — no reconstruction needed._

## Why this is worth publishing (editorial judgment)

"An AI improved my prompts" is a saturated genre. What this repo has
that the genre lacks:

1. **A falsification architecture, not a vibes loop.** Every change was
   pre-registered (hypothesis + decision rule + what must NOT move)
   BEFORE testing. Losers were reverted and ledgered as
   never-blind-retest negative results. Readers can steal this shape.
2. **Receipts for the failures.** The letter-bleed regression the lab
   caused and caught; the +349B rule text that was semantically right
   and still made a 4B model worse (attention tax); the de-anchoring
   idea that got reverted after two runs; two whole batteries voided
   because the laptop was thrashing. Honest failure is the credibility
   engine of the piece.
3. **Findings that surprise practitioners** (each one measured, each
   one transferable):
   - Examples anchor COUNT and TYPE, not just format — an ops example
     with two `create`s made models at EVERY tier emit exactly two.
   - The same deliberation invitation helps one 4B model (trap
     avoidance 44%→75%, ~450B of real pre-JSON thinking) and is
     ignored-or-harmful on another 4B — "4B-class" is not one thing;
     anchor behavior must be an opt-in profile, never a default.
   - A skeleton that violates its own Check line teaches the violation
     (topics said `a.b.c`, phases referenced `a.b` — stable two-sample
     failure until the literal was fixed).
   - "Aim for ≤ 10" reads as a target to fill, not a ceiling — even at
     the strong tier (traps: 11, 10, 9 topics under hard deadlines).
   - Retries in most harnesses are ERROR-BLIND re-sampling — the model
     never sees the rejection message; and at 4B, budgeted re-sampling
     alone rescues ~87-100% anyway (measured), so feedback plumbing may
     only matter at sub-4B.
   - A starved machine produces measurement corruption, not just
     slowness (load 135 → 7/9 driver timeouts that vanished on a
     healthy box): resource checks are data hygiene.
4. **A blind holdout treated as radioactive.** Contamination is
   contextual, not intentional — "I read it but won't use it" does not
   exist for a context window. Session-disqualification rules, blind
   subagent authoring with filenames-only reports, one aggregate bit
   per gate run. Nobody writes about eval hygiene at this level.

## Thesis (one sentence)

If you want an agent to optimize prompts unsupervised, the hard part is
not the optimizing — it is building a measurement system the agent
cannot fool, including the ways it would fool itself by accident.

## Narrative arc (chronological is the honest structure)

1. **Setup: the standing grant.** Owner authorizes continuous
   autonomous improvement with hard rails (never reward hack, holdout
   blindness total, mutual non-regression, one battery at a time).
   The directive file + live-state WORKBENCH pattern: any fresh session
   can resume the campaign mid-experiment. Self-defusing cron heartbeat
   + wakeup pacer; survived a real account-switch usage outage and a
   session kill mid-campaign.
2. **The flywheel turns: drop-diagnosis.** Eleven quality floors fell
   after an iteration; trace forensics split them into three real
   mechanisms + variance; the payload-hash diff trick (compile old and
   new trees, hash per scenario — byte-identical payload ⇒ variance by
   construction). Fixes verified at two local calibers AND the strong
   tier, gates rebuilt in the same commits.
3. **The lab catches ITSELF.** P1 letter-bleed: the lab's own rewrite
   planted abstract letter-paths; 4B models copied them as content
   (5/9→2/9); pre-registered mini-batteries caught it; words-only
   restatement recovered above baseline. Then the +349B/-213B story:
   correct rules that cost accuracy purely by their byte mass.
4. **Manufacturing hard evidence: the trap corpus.** 12 scenarios where
   shallow pattern-completion produces a DETECTABLE wrong answer
   (deterministic per-scenario detectors — no judge needed locally).
   Parallel cold-brief subagent authoring under contamination rules.
   The traps immediately bit the strong tier (0.0 on a dependency-root
   plan; 4-items-for-an-exactly-3-ask under colliding constraints).
5. **The caliber-divergence experiment (6i).** Neutral vs invitation
   anchor, 8 cells, 2 replicates, pre_bytes as the mechanism check.
   Result: adopt as opt-in profile with per-caliber guidance; the
   codex cell deliberately skipped as low-information spend.
6. **Negative results as products.** P11c reverted; retry-feedback
   probe's pre-registered bars turned out unreachable at 4B ceilings —
   and the amendment was recorded BEFORE seeing arm B (adjudication-
   shopping refused, explicitly).
7. **Close: what transfers.** The checklist readers can reuse (below).

## The reusable checklist (the "reader gains something" core)

- Pre-register: metric, threshold, what must stay flat, revert
  condition — in writing, before the test.
- Two directions of non-regression, both gated in CI (quality work
  keeps token gains; token work keeps quality).
- Baselines ratchet; floors never silently lower; refused zeros never
  persist.
- Replicate before adjudicating (single-run variance bands, measured).
- Blind holdout: aggregate-only gate, cold-context authoring,
  contamination = context poisoning (intent irrelevant).
- Deterministic detectors beat judges wherever the wrong answer is
  field-detectable.
- Trap scenarios: reward composing constraints, detect the shallow
  path; add opposite-branch controls so fixes can't overfit one way.
- Ledger negative results with the mechanism; never blind-retest.
- Resource checks before measuring; a throttled machine voids data.
- Per-caliber verdicts from best-in-class models; opt-in profiles for
  caliber-divergent behavior — never model-name routing.

## Numbers to feature (all in git/WORKBENCH; verify at draft time)

- 92-scenario visible corpus, 89 ratcheted floors, mean 0.874.
- gemma reflect 17→20/23 (real-id example); unknown-id class → 0.
- qwen trap-avoidance 44%→75% under the opt-in invitation.
- gemma plan 9/9 (campaign-first perfect battery).
- ~15 commits, every one with local batteries + budget gates green.
- Two voided batteries (machine starvation; 3-way GPU contention).
- 1,709 leaked ssh-agents found by a pre-spawn resource check (the
  "resource checks are data hygiene" cold open — great hook).

## What NOT to claim (honesty guardrails for the post itself)

- No sub-4B win yet (0.8b measurement queued; publish the number
  whatever it is — a capability-floor finding is still a finding).
- The trap pair at the strong tier remains unfixed (two attempts,
  one reverted) — say so; unfinished business is credibility.
- Codex-tier "before" numbers come from single runs with a stated
  margin; don't over-precision them.
- The flywheel had a human owner gating scope, spend, and design
  changes throughout — this is supervised autonomy, not AGI theater.

## Suggested titles (pick at draft time)

- "The Guardrails Are the Product"
- "I let an agent optimize my prompts for 24 hours. Here's the
  measurement system that kept it honest."
- "Pre-register or it didn't happen: running a prompt lab like a
  science lab"

## YouTube adaptation (if made)

- Format: 12-18 min narrated screen walk, not a talking head.
- Cold open: the load-135 ssh-agent fire caught by a pre-spawn check
  (30s), then "this is a story about measurement, not about AI magic."
- Show real artifacts on screen: a pre-registration block in WORKBENCH,
  a battery scoreboard, the letter-bleed diff, the trap detector
  verdicts table, the revert commit for P11c.
- Segment per checklist item is too listy — follow the narrative arc,
  end with the checklist as a downloadable/companion-post pointer.
- B-roll candidates: watch.py scoreboard, `git log --oneline` of the
  campaign day, the WORKBENCH scrolling.

## Production notes

- Source of truth: docs/PROMPT_LAB.md (directive),
  scratch/prompt-lab/WORKBENCH.md (the living lab notebook — quote it
  verbatim; its mid-fight entries are the best material),
  docs/INSIGHTS.md (the distilled findings), git log 2026-07-18/19.
- The WORKBENCH quotes need a pass to strip scenario rubric details
  that would contaminate future holdout authoring? No — holdout
  content never entered these files; visible-corpus detail is fine to
  publish (repo is public).
- Owner voice: first person ("I built"), with the agent as the
  operator inside the owner's guardrails — that framing is both
  accurate and the differentiator.
