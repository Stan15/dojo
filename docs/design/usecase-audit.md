# Use-case lifecycle audit — 2026-07-08

_Owner directive: play out ALL user cases end-to-end (input → serving →
lifecycle/iterations) and find awkwardness, expensive workflows, and
wrong-approach designs. Each case below was traced mechanically against the
implemented behavior, not the intended design. Verdicts: ✅ sound · 🔧 fixed
in this pass · 📒 ledgered (OPEN-PROBLEMS/backlog)._

## A. "I want to learn X" (agent-driven)

Trace: skill triggers → `campaign plan` → agent fulfills → proposal + refinement
questions → user answers → `create --from-task` → `daily` → diagnostic →
practice.

- 🔧 **A1 — refinement answers fell on the floor.** The skill said "after they
  answer: create --from-task" — but materialization uses the ORIGINAL proposal;
  the user's answers went nowhere (the interactive human flow re-plans; the
  agent flow didn't). Fix: skill now instructs a re-plan with the answers as
  `--context` when they change anything.
- 🔧 **A2 — campaign id collision = silent data loss.** Ids derive from the
  first topic's root ("git"); a second git-adjacent campaign would silently
  overwrite the first (`create_campaign` saves unconditionally). Fix:
  `--from-task` ids now slugify the campaign NAME; `create_campaign` refuses to
  overwrite an existing id and uniquifies with a suffix instead.

## B. Same, human at the CLI

Trace: `campaign plan` (TTY) → drain via fulfiller → proposal panel → answer
refinements inline → one re-plan round → confirm → create → offer `daily`.

- ✅ Sound, including the no-fulfiller case (clear guidance, nothing blocks).

## C/D. The daily ritual (agent and human)

Trace: `daily` → tasks (calibration-first, phase-gated, capped) → session →
ready/answer loop → grades → done.

- 🔧 **C1 — reflection never fires by itself (personalization loop was
  open!).** Insights/strategy only move when someone runs `dojo reflect`; the
  skill's "after meaty sessions" is vapor. The blueprint's deterministic
  trigger (attempt-count threshold) was never wired. Fix: `daily` now auto-
  emits ONE reflection task when a campaign has ≥ 5 unreflected attempts
  (separate from the generation cap) — the loop closes mechanically.
- 🔧 **C2 — phase advancement also only ran inside reflect.** A user who never
  reflects would never leave phase 1. Fix: advancement (pure, deterministic)
  is now evaluated during `daily` packet building.
- 🔧 **G2 — stale pending tasks vanished from view.** A grade/generation task
  the agent didn't fulfill yesterday never reappears in any envelope; the loop
  starves silently. Fix: `daily` envelopes now carry `stale_tasks` (count +
  refs) so every morning re-surfaces unfinished AI work.
- 🔧 **D1 — mid-session grading stalls the human loop.** The interactive loop
  drained each grade task serially between questions (~30s pauses). Fix:
  grades queue during the session and drain once at the end ("scoring your
  answers…"), then results display together. (Grades never gated progression
  anyway — scores land async by design.)

## E. Capture ("TIL…", URLs)

Trace: capture (durable first) → route task → proposal → confirm → source +
optional seed.

- ✅ Sound; `--locator` (this pass) carries URL/file provenance to the Source;
  the skill tells agents to fetch/summarize links themselves — dojo never
  touches the network.
- ✅ No-campaigns case degrades to propose_campaign/stay_inbox correctly.

## F. Ingesting material (`dojo add`)

- 🔧 **F1 — ambiguous campaign guess.** With several campaigns and no topic
  match, generation silently landed in whichever campaign listed first. Fix:
  no guessing — ambiguity now returns an honest note asking for `--topic`
  under an existing campaign (deterministic prefix match still auto-resolves).
- 🔧 **F2 — the source was used once and forgotten (grounding continuity
  broken).** `add --generate` emitted one 3-exercise batch but never linked
  the source to the campaign's `sources_config` — all future replenishment
  generated SYNTHETICALLY while the user's trusted material sat unused. This
  quietly betrayed "source-grounded" (north star). Fix: `add` now links the
  source (purpose + topic) so every later replenishment grounds on it.

## G. Grading lifecycle

- 🔧 **G1 — provisional 0.0s poisoned reflection.** Pending-grade attempts
  (grader None) fed the reflect window as failures — the coach would "see"
  losses that are really just ungraded. Fix: reflect rows mark them
  `(ungraded)` and the count is excluded from ctx ids marked reflected.
- ✅ Corrections: additional-review semantics (OP #13, unchanged).

## H. Reflection payload integrity

- 🔧 **H1 — attempts marked reflected without being seen.** The byte budget
  could clip rows out of the payload while ALL ids in context were still
  marked `reflected: true` on apply — evidence silently skipped forever. Fix:
  the compiler now trims the id list to the rows that actually fit; clipped
  attempts stay unreflected for the next run.

## I. Weeks-long progression

- ✅ Advancement now deterministic at daily (C2). 📒 The perpetual
  **maintenance phase** after the last phase (ADR 005) remains unimplemented —
  today the final phase persists indefinitely, which is behaviorally close but
  doesn't shift strategy to low-scaffold maintenance. Backlog.

## J. Skill-lane stock

- 🔧 **J1 — daily-generated skill stock was unreachable (lane starved!).**
  Replenishment landed as candidates; nothing in the daily loop promotes
  candidates, so skill topics generated stock nobody could practice. Fix per
  blueprint I2 ("policy may auto-accept, the gate is recorded"): daily
  replenishment tasks carry `auto_promote`; the applier creates exercises
  directly with `quality="auto_accepted"` (recorded), respecting the queue
  cap with an honest skip count. Bulk `add --generate` material keeps manual
  review — trust policy differs by volume and origin, deliberately.

## K–P. Multi-campaign, absence/return, review, benchmark, export, offline

- ✅ Interleave + boosts + atrophy re-entry play out correctly (packet caps
  absorb the return-after-a-month flood with honest overflow counts).
- ✅ Offline: recall practice proceeds; skill lane waits with pending tasks.
- 📒 Interleave share (top campaign gets cap−N+1) is front-heavy; revisit with
  real usage data rather than tuning blind.

## Q. Cost & store lifecycle over months

- 📒 **Q1 — tasks/ grows forever** (1–3 files/day + per-answer grade tasks).
  Harmless functionally (indexed), but the store deserves housekeeping:
  archive fulfilled tasks older than ~30 days. Backlog with doctor check.
- ✅ Token spend per day is bounded by design: ≤ 2 generation + ≤ 1 reflect +
  per-answer grades, all budgeted payloads (~0.5k tokens each), visible in
  `dojo stats`.
- ✅ Attempt/insight growth: reflect window and insight digests are capped, so
  prompt sizes do not grow with history length.

## The one structural observation

Several fixed bugs (C1, C2, G2, J1) share a root: **loop-closing steps lived in
commands nobody is obligated to run.** The correction applied throughout: any
step the loop depends on must either happen deterministically inside `daily`
(the one command the ritual guarantees) or be re-surfaced by it every morning.
`daily` is the heartbeat; everything vital now beats with it.
