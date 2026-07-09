# QUESTIONS for the product owner

Non-blocking. Each open question has the default I will proceed on if unanswered.

## Open

1. **Fulfiller runner** (was "subprocess connectors" — refined per your 2026-07-07
   notes, which changed my recommendation):

   Your three concerns, answered:
   - **Unified interface: guaranteed.** The task contract is the only interface.
     Every fulfiller — harness in conversation, agent cron job, or local model —
     does the identical three steps: read the task's prompt → produce JSON →
     `dojo task submit`. Nothing is stratified; the runner below is just an
     *automation* of those three steps, not a second pipeline.
   - **The .sh wrapper was a symptom, and it dies.** The prototype needed wrapper
     scripts because its connector protocol demanded custom I/O framing. Under
     the task contract, dojo owns the plumbing: it runs your command, pipes the
     prompt to stdin, reads stdout, extracts the JSON, and submits it through the
     same validated path. Config becomes **one string**:
     `dojo config set fulfiller.command "ollama run llama3"`. No shell file, no
     protocol to learn. (A wrapper remains *possible* for exotic tools, never
     required.)
   - **Agent cron is the harness path, not a connector use case.** A scheduled
     agent (Hermes cron / Claude Code scheduled task) running `dojo daily --json`
     fulfills tasks itself — zero setup beyond the skill. So the runner only
     serves one persona: plain system cron or CLI user with a local model and
     **no agent at all**.

   Consequence: the old `connectors.py` (~500 lines: own protocol, progress UI,
   input modes) is deleted either way. The remaining decision is small:

   **Ship `dojo task run` (one-string-config runner, ~100 lines) in v1, or tag it
   backlog until a real agent-less user asks?**
   **My recommendation & default: ship it in v1** — it is cheap against the new
   contract, it makes `dojo` complete without any agent, and it is the natural
   test harness for the task contract itself (we can drive it with a mock command
   in CI). agree
   → **Shipped**: `dojo task run` exists (cli.py, `--command/--limit/--timeout`,
   falls back to `fulfiller.command` config). Moving to answered.

1. **Version tag**: all planned milestones are delivered and verified; corpus
   wave 4 + reflect-prompt work remain from your directives. Tag `v0.2.0` now
   and reserve `v1.0.0` for after that work, or hold tags entirely?
   **Default: tag v0.2.0 at the next natural pause.** ok

1. **Plan/strategy change authority** (your 2026-07-09 question: "don't want
   things changing under the user's feet"). Findings: strategy-dial restraint
   is well-benchmarked (4 pattern-only reflect scenarios), but (a) the corpus
   NEVER rewards a plan revision — every good reference has `plan_revision:
   null`, an ossification bias; (b) `apply_reflect` applies whole-plan
   replacements SILENTLY (service.py), unlike plan/route which use
   review-before-trust; (c) reflection has no question channel — the
   meta-learning escape hatch exists only in generation; (d) the syllabus is
   never AI-rewritten at all (no field for it), so that surface is already safe.

   Proposed: **tiered change authority.**
   - Tier 0 (silent+journal): insights, difficulty/scaffolding dials — moving
     these IS the product; already benchmarked.
   - Tier 1 (apply+notify+undo): mechanically-minor plan edits — additive/
     cosmetic only (append phase/topic, focus text, relaxed criteria); journal
     stores plan_snapshot; next daily announces; revert command.
   - Tier 2 (proposal, like routes): destructive/reordering revisions await
     `dojo plan confirm`; rest of the reflection still applies. Fast path: if
     evidence cites the user's OWN words (attempt.feedback / feedback.user.* /
     an answered meta-question) it is user-initiated → Tier 1.
   - Tier 3 (ask, don't propose): inferred structural need with no explicit
     evidence → bounded `questions` channel on ReflectResult (mirror of
     generation's Intervention); questions become diagnostic items; answers
     become citable evidence for a later Tier-2/1 revision.
   - Anti-drip rail: cumulative delta vs the last user-confirmed plan snapshot
     escalates repeated "minor" edits to Tier 2. Deterministic, unit-tested.
   - Corpus wave 4 additions: `legitimate_restructure` (explicit deadline
     feedback → good output DOES revise, citing it), `inferred_restructure_probe`
     (structural mis-fit pattern, zero feedback → good output asks a
     meta-question; bad silently rewrites).

   **Default: implement the tiered model with corpus wave 4 (STATE item 2) —
   rails first (pure code+tests), then prompt + scenarios.**

1. **Post-packet appetite: `dojo more`** (your 2026-07-09 question). Today:
   re-running `dojo daily` drains due items the packet cap held back (works);
   `dojo start` serves unattempted material + replenishment (undiscoverable);
   when nothing is due there is NO sanctioned path — "the schedule is honest"
   ends the day. Proposal: a `dojo more` bonus packet, explicitly labeled,
   priority order: due-remainder → unattempted/candidates → fresh generation
   on the weakest topic (max ONE task — token frugality) → soon-due
   pull-forward (FSRS credits early reviews natively; no schedule
   corruption). I9 reasons on every item ("ahead of schedule by 18h").
   Never re-drills today's completed reviews (near-zero retention value;
   protects the honest-schedule signal). `daily` stays the only ritual;
   `more` is never suggested unsolicited.
   **Default: build `dojo more` after the current docs/README directives,
   before the eval re-baseline.**

   **Known risks under heavy use (owner asked 2026-07-09; analysis only, no
   fixes yet — these gate the implementation):**
   - *Binge evidence distorts the learner model*: Attempts carry no
     session-context marker; reflection's sliding window can fill with
     fatigue/novelty-mode rows and auto-reflect (≥5 unreflected) can fire off
     a single binge, recalibrating from unrepresentative data.
   - *Queue churn discards practiced memories*: `_enforce_queue_limit`
     archives OLDEST by created_at regardless of FSRS state — heavy
     generation+promotion replaces consolidated memories with fresh generic
     items; consolidation loses to novelty, silently.
   - *Cross-campaign review-debt compounding*: per-campaign caps (~20-30)
     don't bound the global due-count against the daily packet cap (8);
     appetite across campaigns can create a permanent "held back" backlog
     (Anki-style collapse).
   - Secondary: samey thin-topic generation → skip-row noise in reflection;
     just-reviewed floods briefly inflate the stats retention estimate.
   Root cause is provenance blindness (ritual vs appetite evidence;
   consolidated vs disposable items) — the implementation must mark and
   weight, not just cap.

## Answered (2026-07-07)

- **Grading source of truth** — AI grades against rubric when a harness is
  present; self-report fallback offline; `dojo correct` overrides. *(agreed)*
- **Daily packet size** — 5 default, hard cap 8, `daily.packet_size` config. *(agreed)*
- **`archived_implementation/`** — stays in-tree for easy reference until the
  owner clears it; excluded from packaging/tests. Blueprint M1 updated.
- **Python floor** — 3.11. *(agreed)*
- **Capture routing** — routes are proposals awaiting **confirmation by default**
  (inline in conversation or via `dojo inbox`); `capture.autofile: true` opts into
  auto-filing. ADR 013 + blueprint §8 updated.
- **SR scheduling library** — reuse over build: **py-fsrs** (MIT, official FSRS-6
  reference impl) behind a dojo-owned boundary. ADR 014.
- **Anki integration** — no live sync (would split scheduling authority and starve
  the evidence loop); deck **import** and one-way **export** are backlog. ADR 015.
