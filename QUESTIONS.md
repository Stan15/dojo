# QUESTIONS for the product owner

Non-blocking. Each open question has the default I will proceed on if unanswered.

## Open — decisions actually waiting on you

1. **v1.0.0** — your stated condition (quality iteration) is met: visible
   corpus 55 scenarios, floors ratcheted, holdout standing. Remaining step:
   run the holdout release gate once (first run = floor bootstrap + gap
   verdict, ~76 codex calls), and if the gap is healthy (≤ 0.1), tag.
   **Default: run the gate + tag v1.0.0 at your go-signal; I don't trigger
   this spend unprompted.**
2. **Anki interop** — full PM + engineering investigation delivered at your
   direction (2026-07-09): `docs/design/anki-interop.md`. Headline: possible
   (apkg = zip+SQLite, stdlib parser); feasible (2-3 sessions for import,
   1 for export); ideal **as a scoped acquisition adapter, not a sync
   surface** — and modern Anki now runs FSRS natively, so dojo (py-fsrs,
   same model family) can honor a deck's memory state near-losslessly:
   "your memories transfer intact" is a pitch no non-FSRS competitor can
   make. Bulk collection import is explicitly rejected (would break packet/
   debt-guard honesty); import is deck→campaign scoped. Four sub-decisions
   listed in the doc §8. **Default: parked until you promote it.**
3. **Repo visibility** — the repo is private by your choice; the README's
   curl one-liner activates only when public. Any timeline?
   **Default: stays private; no action.**
4. **Weak-floor iteration budget** — honest weak floors on the visible
   corpus, all with driver traces recorded for analysis: reflect_learner_
   language 0.10, generate_downward_calibration 0.30, reflect_diagnostic_
   voice_revision 0.33, extension-binge 0.00, learner-contradicts 0.33,
   single-fact-goal 0.44, diagnostic-kind pair ~0.60 (never-iterated
   prompt), grade_learner_language 0.67, pending-grade 0.64. The language
   floors suggest the one-line language rule needs reinforcement; the
   diagnostic prompt has never had an iteration pass. It's a codex spend
   session. **Default: next session you green-light eval spend.**
5. **CLI/UI i18n** — learner-facing TASK OUTPUT follows the learner's
   language (shipped); the CLI shell itself (labels, help, completion
   message) is English. Full i18n is a product surface decision.
   **Default: English shell; revisit on real non-English usage.**
6. **Strategic tier timing** — Postgres backend (bounded by the conformance
   suite), the app, dojo-side PDF/EPUB ingestion (agents already cover it by
   reading + capturing). All owner-gated.
   **Default: none started without your call.**

_Parked by your explicit rule (not decisions, just recorded): interleave
share tuning and OP #13 exact-undo — both wait for real usage data._

## Decided & shipped — 2026-07-09 ledger (detail preserved)

1. **Anti-reward-hacking: holdout evals + corpus enrichment** (owner
   directive 2026-07-09: "the prompts shouldn't reward hack; create a
   holdout set; highly enrich the evals"). The risk is real and this
   session demonstrated it: prompt iteration reads the visible rubric
   verdicts, so a prompt can learn THE TEST (the rushing carve-out's
   wording sits close to its scenario's rubric — general principle, but
   the pattern is the hazard). Shipped:
   - **Holdout tier** `corpus/holdout/` + tests/test_evals_holdout.py:
     own marker (`-m eval_holdout`, excluded from default and from
     `-m eval`), own baseline `<pair>__holdout.json`, reports prefixed
     `holdout-`. THE PROTOCOL (in the module docstring): never run/read
     during prompt iteration; run at release gates only; a visible-vs-
     holdout mean gap = overfitting — generalize the failing skill, never
     fix the named scenario; a holdout scenario whose verdicts drive a fix
     is burnt → migrate to visible, author a replacement; authored by a
     subagent and committed UNREAD by the prompt author (mechanical QA:
     shape suite + judge calibration gate).
   - **Enrichment** (12 visible scenarios, category "robustness" + others):
     wordy/terse/JSON-bearing/injection-bearing answers, right-answer-
     wrong-method, non-Latin script, mixed reflection signals, learner-
     contradicts-evidence, mixed-language and single-fact goals, junk
     captures, extension-binge discounting.
   Floors bootstrapped once per set (codex, batched — spend policy).
   **Language policy** (your follow-up, 2026-07-09): identifiers and
   instructions stay English for performance — topic paths and insight keys
   are already mechanically ASCII (`[a-z0-9_]` validators), and the
   templates stay English (instruction-following is strongest there at
   every model caliber). Everything ADDRESSED TO THE LEARNER follows the
   learner's language: grade feedback (language of ANSWER), plan missions
   and refinement questions (language of GOAL), insight text / clarifying
   questions / journal (language of their answers and FEEDBACK). One rule
   line added to each learner-facing template; benchmarked by
   plan_goal_in_learner_language (Spanish-mix goal → Spanish mission and
   question over English-splained ones). Full CLI/UI i18n stays backlog —
   product surface, separate decision.

1. **Model-output traces with provenance** (your 2026-07-09 question: "a
   model might fetch a website, do whatever, before the final JSON — JSON
   may not be all it outputs"). Analysis of the core need:
   - Entity→task provenance already exists everywhere (insight/exercise
     `generation_run`, plan journal `task_id`, capture `proposal.task_id`)
     — but the task discards the model's actual words: `submit` keeps
     `response_bytes` and truncated error strings, never the raw text. The
     audit chain dead-ends one hop before "what did the model say?".
   - **Boundary principle**: dojo's provenance domain is the TASK BOUNDARY.
     The harness's intermediate steps (fetches, tool calls, its own
     reasoning turns) happen in the harness's context — invisible and
     unverifiable to dojo, by design (ADR 009/010 single-turn value
     injection keeps the injection surface closed). Demanding them would
     break install-and-it-works and record unverifiable claims. What
     crosses the boundary is the SUBMISSION — and unknown-caliber models
     wrap their JSON in prose (why extract_json exists): reasoning,
     "I fetched X", partial work. That text IS the trace.
   - Material provenance beyond the boundary already has its honest,
     agent-supplied channel: `capture --locator` (the agent tells us where
     it read; dojo never fetches). No new channel needed.
   **Design (implemented same day)**: every submission — accepted AND
   rejected — is persisted verbatim on the Task entity (`trace` list:
   timestamp, ok, errors, raw), TAIL-clipped at TASK_TRACE_CLIP_BYTES
   (heads are prompt echoes; answers and their surrounding reasoning live
   at the end), truncation marked (I10). On the entity, not a sidecar
   file, so I7 round-trip, `dojo export`, and future backends carry it for
   free; `submit` stays the only writer (I5). The missing link closed:
   attempts record `grade_run` when an AI grade lands. Surfaces:
   `dojo task show <id> --trace` renders the submission history;
   `dojo insights show` names the generating task and the trace command —
   belief → verbatim answers → generating task → the model's own words.
   Storage: tasks/ already grows forever (ledgered housekeeping backlog
   now includes traces — same cleanup, richer payoff).

1. **Generate prompt OUTPUT skeletons from code?** (your 2026-07-09 question —
   motivated by the day's finding that every eval failure was a validator the
   template never stated). My analysis: full generation is the wrong fix —
   (a) it inverts your own 2026-07-07 requirement that prompts are editable
   markdown artifacts (iteration never touches Python); (b) INSIGHTS
   2026-07-07: skeletons beat formal schema dumps for weak models precisely
   because they're CRAFTED (elisions, inline comments, per-mode emphasis) —
   generation doesn't delete that editorial content, it relocates it into
   Field metadata where it's harder to read, iterate, and review; (c) the
   skeleton phrasing is load-bearing for the judged 0.835 mean — mechanical
   regeneration risks silent quality regressions that cost real eval money
   to find; (d) the context-aware branching you want already IS code: the
   compiler chooses templates/fragments per mode.
   **Proposed instead — single-source the CONSTRAINTS, verify the TEXT:**
   - Refactor per-schema word caps/counts (limits.py + scattered
     `_cap_words` validators) into ONE declarative table per result schema;
     validators derive from it. Change a cap in one place.
   - Add a drift-gate test: for each task kind, every declared cap's literal
     number must appear in its template, and every schema field name must
     appear in its OUTPUT block. A template that forgets a floor goes red at
     commit time instead of failing a live model.
   - Escalation if drift ever recurs: a compiler-injected `{{ limits_line }}`
     footer generated from the declaration (structurally impossible to omit
     floors; skeleton stays editorial). Not the default — costs bytes and
     moves text out of the editable artifact.
   **Default: declarative caps + drift-gate test, next session.**
   → **Answered + shipped 2026-07-09** (owner: "i agree with you", with one
   refinement that improved the design: templates should not know about
   every limit — interpolate exactly the limits each prompt needs, where it
   needs them). Implemented: `limits.TEMPLATE_CAPS` (kind → placeholder →
   constant, single source; guidance numbers stay literal prose), the
   compiler injects each kind's caps at render (existing `{{ }}` machinery,
   `{{ window_n }}` precedent), templates now interpolate their own floors
   only, and two gates in test_prompts.py: every declared cap must appear
   as a placeholder in its template (a floor can't go unstated), and a
   declared cap's literal value must not ALSO appear hard-coded ("≤ N
   words") — the drift vector is patrolled, not just discouraged.

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
   → **Shipped 2026-07-09**: `dojo learn` (goal.route task kind, 3 KB
   registry-validated payload; applier writes nothing on a near fit —
   `dojo learn extend|new <task-id>` resolve the extend-or-start-fresh
   question; extend = topic + appended phase journaled PLAN_APPLIED under
   authority, announced by daily, revertable; propose_campaign auto-chains
   a seeded campaign.plan task; `--new`/empty registry skip routing;
   interactive `learn_flow` for the TTY audience).
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
   → **Shipped 2026-07-09**: `dojo more [--force]` + the spec'd
   daily-completion message (agent copy verbatim, status
   "complete_for_today"; human copy in interactive). Debt guard global
   (`_review_load_7d`: item + skill-topic FSRS dues incl. overdue vs
   packet×7×`pacing.headroom`), sourcing unattempted→candidates→ONE
   generation on the weakest graded topic (auto-promote), once per calendar
   day (`--force` overrides the guard with the projection printed, never
   the daily cap), refusal is `ok: true` with projection + `dojo start
   --topic` alternative. Extension attempts carry `origin: "extension"`
   (round-trip pinned) and reflect rows label them. One refinement: a
   pending plan PROPOSAL hint still appends to the completion `next` —
   consent questions repeat until resolved; they are not practice
   solicitation.
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
       "✓ Done for today.
        Coming back tomorrow is what makes it stick.
        Go touch grass. 🌱  (Genuinely still hungry? Run `dojo more` — it
        only says yes when your review budget agrees.)"
     Line 1 is static — no variants.
     Agent (--json): {ok: true, session: null, status: "complete_for_today",
       next: "today's practice is complete — tell the learner it's done,
       playfully (go touch grass); tomorrow's session is what makes it stick
       (consistency beats volume); do not offer more practice unprompted; if
       the learner explicitly asks for more, run: dojo more --json"}
     (The agent line binds the HARNESS to the no-solicitation rule too.)
     Line 1 is fully static (owner rulings 2026-07-09): the item count was
     cut (always N of N — filler that reads as a score) and the STREAK
     COUNTER was cut too — a consecutive-days number directly above "come
     back tomorrow" is don't-break-the-chain pressure however gently
     worded; a no-guilt rule can't remove the loss-anticipation a live
     counter creates. Line 2 carries consistency as a PRINCIPLE instead of
     a score. **Push surfaces get principles; pull surfaces get numbers**:
     the streak stays a real derived fact (consecutive practice days from
     attempt timestamps, no stored counter) and lives in `dojo stats`,
     which the user consults by choice. Broken streaks are never mentioned
     anywhere, on any surface.
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
   → **Shipped 2026-07-09**: `dojo insights [--all] [--campaign]` /
   `insights show <id>` (receipts verbatim + grader + effect counts) /
   `insights resolve <id> --because` (stored verbatim in a new
   `Insight.resolution` field, round-trip pinned; fed to the next
   reflection as `[learner resolved insight <key>]` feedback,
   timestamp-gated against the last REFLECT). Announce-once via
   `insights_changed` on REFLECT journal entries. Generation stamps
   `targeted_insights` keys in task context — and the selection was
   UPGRADED (owner probe 2026-07-09): top-K now ranks by topic affinity to
   the generation target, then `updated_at` (evidence freshness), replacing
   the old created_at-order tail.

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
   → **Shipped 2026-07-09**: `dojo campaign list` (status/phase/retention/
   due/idle dashboard) + `campaign archive <id>` (TTY confirms; agents relay
   the learner's explicit ask). Completion is deterministic and OBSERVED:
   all-phases-passed flips status → "maintenance" (ADR 005: reviews trickle,
   never-practiced stock and generation excluded; maintenance dues still
   count as review debt for `dojo more`'s guard) and daily announces the
   three doors once. `dojo learn extend` on a maintained campaign reopens it
   (the extend door). Windowed-criteria fix: phase accuracy over the last
   2×min_attempts graded attempts (provisional grades excluded) — a rough
   start ages out. Idle notices (≥`campaign.idle_days`, default 14) are
   neutral facts with doors, no guilt vocabulary.

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
