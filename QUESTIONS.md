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
   → **Shipped 2026-07-09** (owner: "we need to address this"): rails in
   tasks/authority.py + gated apply_reflect + `dojo plan` lifecycle + daily
   surfacing; reflect prompt gained PLAN section, revision evidence rule, and
   the questions channel; corpus wave 4 change-authority scenarios landed.
   One refinement to the ledgered design: learner-voice evidence includes
   answers to DIAGNOSTIC questions (the system asked, the learner told it) —
   this is what makes onboarding calibration and the Tier-3 question loop
   compose.

1. **Route-first entry for learning goals** (your 2026-07-09 question):
   → **Owner-approved 2026-07-09** ("i agree with everything") — directed work, STATE item 1.
   "I want to learn xyz" should hit the ROUTER first, not `campaign plan`.
   Close fit → harness relays "looks like <campaign> › <topic> — extend or
   start fresh?"; extend = new_topic + appended phase (a MINOR additive plan
   change under change authority: auto-applies, announced, undoable); "no,
   new" or router `propose_campaign` → hand off to the FULL campaign.plan
   pipeline seeded with the goal + router's name/mission hints (never
   filing's bare-campaign path — that stays for material captures only).
   Skip routing when zero campaigns exist or the user explicitly says new.
   Rationale: prevents semantic campaign sprawl (the sibling of audit A2's
   id collisions), cheapest task first (3 KB, registry-validated), one
   consent grammar with plan authority.
   **Default: implement as `dojo learn` orchestration right after the
   change-authority milestone (prompt+corpus) completes.**

1. **Post-packet appetite — SUPERSEDES the `dojo more` bonus-packet design
   below** (your 2026-07-09 "core need" question).
   → **Owner-approved 2026-07-09** — directed work, STATE item 2.
   The foundational need is
   a CAPACITY CHANNEL: the learner's daily time/energy varies and the system
   has no input for it ("more" and "too much" are the same missing channel).
   Split the budgets: RETENTION (reviews due) is fixed by memory science —
   appetite can't buy more and re-drilling today's items is worthless;
   ACQUISITION (new material) is a real preference dial, and every unit is
   review debt on days 3/7/21. Mechanism:
   - Session-complete summary offers a bounded acquisition top-up: up to
     `daily.extension_cap` (default 3) NEW items — unattempted stock →
     candidates → at most ONE generation task.
   - **Debt guard (the invariant)**: grant only if projected due-load over
     the next ~7 days (computable from FSRS state) stays within packet
     capacity × `pacing.headroom`. Otherwise refuse HONESTLY with the
     projection, and offer the free alternative: `dojo start --topic`
     (targeted retrieval costs no new debt). Guard is global — exactly where
     the per-campaign caps have their hole. Override flag prints the debt
     first (inform, don't infantilize).
   - Pacing anxiety ("packet too slow for my deadline") routes to the PLAN
     conversation (deadline feedback → reflection → consent-gated revision),
     not to volume.
   - This structurally answers all three ledgered `more` risks: bounded K of
     new items (no binge evidence floods), debt-gated generation (no churn),
     global guard (no Anki collapse).
   **Interface spec (owner asked for exact shape, 2026-07-09):**
   - **AT-REQUEST ONLY (owner ruling 2026-07-09, agreed): the system never
     SOLICITS extra practice — it only answers requests.** An offer
     manufactures appetite; a request reveals it; closure is part of the
     method; nudged extensions corrupt the origin marker. Therefore: NO
     session-end [y/N] offer, NO proactive capacity block in answer/daily
     envelopes. One verb, **`dojo more`**, discovered via a passive mention
     (statement, never a question) in the daily-completion message.
   - **Daily-completion message** (re-running `daily` when today is done) —
     exact copy, short, lesson implicit, concession last:
     Human (playful "touch grass" tone; `dojo more` styled as a COMMAND —
     bold/cyan via rich, backticks in plain text):
       "✓ Done for today — 5 of 5, streak intact.
        Coming back tomorrow is what makes it stick.
        Go touch grass. 🌱  (Genuinely still hungry? Run `dojo more` — it
        only says yes when your review budget agrees.)"
     Agent (--json): {ok: true, session: null, status: "complete_for_today",
       next: "today's practice is complete — tell the learner it's done,
       playfully (go touch grass); tomorrow's session is what makes it stick
       (consistency beats volume); do not offer more practice unprompted; if
       the learner explicitly asks for more, run: dojo more --json"}
     (The agent line binds the HARNESS to the no-solicitation rule too.)
     Dynamic values (owner asked 2026-07-09): "5 of 5" = the completed
     session's real counts (skips count — engagement, not absence). Streak =
     DERIVED consecutive practice days from attempt timestamps (no stored
     counter exists or is needed). **No-guilt rule**: show "day N in a row"
     only when N ≥ 2 and true; day-1/post-gap runs simply omit the streak
     clause — a broken streak is NEVER mentioned (absence shows up as
     gentler scheduling, not commentary).
   - `dojo more --json` returns a normal session envelope with items
     origin:"extension", or the refusal block with ok:true (no is an answer,
     not an error): {extension_available: false, projected_due_7d,
     capacity_7d, reason, alternative}. `--force` overrides but always emits
     the projection first. Ships together with the completion message (a
     message never names a command that doesn't exist).
   - Guard: projected_due_7d + K ≤ packet_size × 7 × pacing.headroom(0.8),
     global across campaigns, counting existing FSRS dues incl. overdue.
   - Sourcing order: unattempted → candidates → max ONE generation task on
     the weakest topic. Never today's reviews; no pull-forward. Once per
     calendar day. Extension attempts carry an origin marker (reflection can
     discount appetite-mode evidence).
   **Default: build the capacity channel (extension + debt guard) INSTEAD of
   `dojo more`, after route-first entry.**
   Independent defect found during this analysis, ledgered in OPEN-PROBLEMS:
   `_enforce_queue_limit` archives oldest-by-created_at regardless of FSRS
   state — it can discard consolidated memories to make room for fresh
   generations today, no appetite feature needed.

1. **Insight visibility with provenance** (owner-directed 2026-07-09:
   "insanely well thought out visibility tools so user feels complete
   ownership over their learning"). The learner model personalizes
   everything yet is invisible today (stats shows only a COUNT; no insights
   command exists). Design — inspectable, traceable, contestable,
   consequential:
   - SEE: `dojo insights [--campaign] [--all]` — the model grouped by topic:
     key, description in the model's recorded words, status, age, evidence
     count, last-cited. Resolved insights under --all (what you overcame is
     part of ownership).
   - TRACE: `dojo insights show <id>` — the receipts card: every evidence
     attempt rendered as date · prompt · the learner's VERBATIM answer ·
     score · grader (I10) · error_tag. All data already stored
     (insight.sources → attempt ids; attempts keep prompt + user_answer).
     "We believe this because on these occasions you wrote this."
   - CONTEST: `dojo insights resolve <id> --because "..."` — learner override
     is highest authority; the reason stored verbatim, fed to the next
     reflection as learner-voice feedback. ALSO advertise: insights are plain
     markdown files — direct edits are first-class (conformance-tested).
   - EFFECT: daily announces insight creates/updates once ("reflection
     updated 2 beliefs about you — dojo insights") via the same
     announce-once machinery as plan changes (Tier-0 applies silently;
     silent ≠ invisible). Forward tracing gap: generation doesn't stamp
     which insights it targeted — record targeted insight keys in generation
     task context so `insights show` can say "3 exercises this week targeted
     this" (the visible-work moment).
   **Default: implement alongside campaign lifecycle (both are the
   ownership/visibility block, STATE item 3).**

1. **Campaign lifecycle: view, complete, archive** (your 2026-07-09 question).
   → **Owner-approved 2026-07-09** — directed work, STATE item 3.
   Findings: there is NO `dojo campaign list` (campaigns visible only via
   stats), and `store.campaigns.archive()` exists but is unexposed. Your
   mechanism, refined:
   - Detection is DETERMINISTIC, not a generation meta-question: all-phases-
     passed is pure math (active_phase_index ≥ len(plan)) — daily announces
     completion like it announces plan proposals. Reflection's new
     `questions` channel handles the SOFT signals (mission drift, long idle:
     days_since_practice is already computed).
   - Reflection never PERFORMS the archive — AI proposes, learner disposes
     (same authority grammar as plans). Archive = "I accept forgetting";
     always a human command/confirm.
   - Completion offers three doors: **maintain** (default — no new material,
     retention trickle only; this is ADR 005's maintenance phase), **archive**
     (leave rotation, git keeps history), **extend** (feeds the route-first
     learn flow).
   - Ship: `dojo campaign list` (status/phase/retention/idle), `dojo campaign
     archive <id>` (+confirm), completion + idle notices in daily,
     maintenance status per ADR 005.
   - Include the **windowed-criteria fix** (owner asked "can the end state
     be reached?", 2026-07-09): phase advancement currently averages accuracy
     over ALL attempts ever on the phase's topics — a bad start drags a
     lifetime mean and can stall the final phase long past current ability.
     Evaluate criteria over a recent window (ADR 008 style) so completion is
     reachable in time proportional to current performance. Also: today
     NOTHING observes active_phase_index == len(plan) — a finished campaign
     silently keeps practicing/replenishing; the completion notice is what
     makes the end state real.
   **Default: implement after route-first entry and the capacity channel —
   it composes with both.**

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
