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
   in CI). 

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
