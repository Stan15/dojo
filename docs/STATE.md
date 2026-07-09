# STATE

_Last updated: 2026-07-09 (learn session). Trust this snapshot; git
history carries the detail._

## Phase

**Implementation — v1 feature-complete and shipped to main.**
All blueprint milestones M0–M6 delivered and E2E-verified; plus (owner-directed,
post-blueprint): three-tier eval system with `dojo benchmark`, interactive human
CLI, capture/inbox with `--locator`, export/uninstall, token-footprint gates,
the use-case lifecycle audit with its 10 fixes, the **documentation
system** (ProperDocs+Material+mkdocstrings site via `mise run docs`; 100%
public-surface docstrings gated by tests/test_docs_coverage.py; README
currency-audited), **plan change authority** (tasks/authority.py; the
plan is a consent-gated contract), **route-first entry** (`dojo learn`;
a goal routes against the registry before any new campaign is planned), and
the **capacity channel** (`dojo more`; at-request-only, debt-guarded), and
the **ownership block** (`dojo insights` with receipts; campaign lifecycle
with deterministic completion → ADR 005 maintenance).
**344 tests green** + 28 eval-marked.
Repo is PRIVATE (owner's choice) — install via checkout `sh install.sh`;
owner's machine runs the current build.

## What the system is now (one paragraph)

Deterministic core (scheduling via py-fsrs, packet building, validation,
storage as git-versioned markdown) + AI-as-validated-tasks (ADR 010: any
model fulfills compiled, byte-budgeted prompts through one `task submit`
door). `dojo daily` is the HEARTBEAT: builds the bounded explained packet,
advances phases, auto-emits reflection at ≥5 unreflected attempts,
re-surfaces stale tasks, auto-promotes+grounds replenishment. Agents drive
via SKILL (always `--json`, extract-never-enrich); humans get interactive
flows on the same machinery (structurally impossible to block an agent).
AI plan restructures are consent-gated (minor/asked-for auto-apply with
undo; major inferred await `dojo plan confirm`; reflection can ASK via its
questions channel). Quality is guarded by ratcheted per-(driver,judge)
baselines over a 26-scenario judged corpus + compliance corpus + golden
payload/footprint pins.

## NEXT ACTIONS (in order)

_Done this session: directives 0a (docs system — went MkDocs→**ProperDocs**+
mkdocstrings after owner said "use the absolute best, not the easiest"; MkDocs
is abandoned upstream, ProperDocs is the maintained continuation — see
INSIGHTS 2026-07-09) and 0b (README audit). `dojo task run` confirmed already
shipped (QUESTIONS Q1 → answered)._

_Also done 2026-07-09 (owner-directed): **plan change authority** shipped —
tasks/authority.py rails (minor-additive auto-apply + snapshot + announce +
`dojo plan revert`; major inferred → proposal for `dojo plan confirm|reject`;
learner-voice evidence fast path incl. diagnostic answers; anti-drip vs the
last CONFIRMED baseline), ReflectResult `questions` channel → diagnostics,
reflect prompt now SHOWS the plan (was blind; footprint 1967→2523B,
deliberate), corpus wave 4 change-authority category (2 scenarios, floors
raised). 283 tests green._

_Items 1–3 are OWNER-APPROVED directives ("i agree with everything",
2026-07-09) — execute them from their QUESTIONS.md designs; they are
committed work, not proposals awaiting an answer. Item numbering is stable
(QUESTIONS.md cross-references it)._

1. ✓ **DONE 2026-07-09 — Route-first entry (`dojo learn`) shipped**:
   goal.route task kind (3 KB, registry-validated, RouteResult contract),
   review-before-trust applier (near fit → extend-or-start-fresh question
   resolved by `dojo learn extend|new <task-id>`; extend = deterministic
   topic+phase append journaled PLAN_APPLIED under authority,
   daily-announced, revertable; propose_campaign chains a seeded
   campaign.plan task), `--new`/zero-campaign skip, interactive learn_flow,
   SKILL.md goal section rewritten (footprint baseline 3735→3902,
   deliberate). 306 tests green.
2. ✓ **DONE 2026-07-09 — Capacity channel (`dojo more`) shipped** per the
   QUESTIONS.md spec: at-request-only top-up (unattempted → candidates →
   ONE generation on the weakest graded topic), global 7-day debt guard
   (items + skill topics, incl. overdue, vs packet×7×`pacing.headroom`),
   honest `ok: true` refusal with projection + `start --topic` alternative,
   once per calendar day (`--force` overrides the guard never the cap),
   `origin: "extension"` on session+attempts (round-trip pinned; reflect
   rows labeled), spec'd completion message verbatim on both surfaces
   (status `complete_for_today`; plan-proposal hints still append — consent
   ≠ solicitation). **The system never solicits extra practice** — still
   binding for all future surfaces. 325 tests green.
3. ✓ **DONE 2026-07-09 — Ownership/visibility block shipped** (both halves,
   details in QUESTIONS.md):
   a. Insights: `dojo insights [--all]` / `show` (verbatim receipts + grader
      + forward-effect counts) / `resolve --because` (stored verbatim in
      `Insight.resolution`, round-trip pinned; feeds the next reflection as
      learner-voice, timestamp-gated); Tier-0 changes announce once in
      daily; generation stamps `targeted_insights` (selection upgraded:
      topic affinity → updated_at, replacing created_at-tail — owner probe).
   b. Lifecycle: `campaign list` / `archive` (+TTY confirm); deterministic
      completion → **maintenance** (ADR 005: reviews trickle, no new
      material/generation; dues still count in `more`'s debt guard); daily
      announces the three doors once; `learn extend` reopens a maintained
      campaign; windowed criteria (last 2×min_attempts graded, provisional
      excluded); neutral idle notices (`campaign.idle_days`=14).
   344 tests green.
4. ✓ **DONE 2026-07-09 — eval re-baseline + triage**: fresh (codex,codex)
   pair baseline committed — quality mean **0.823** over 26 scenarios (was
   0.732), compliance 4/4 = 1.0. All three initial failures were INVISIBLE
   VALIDATION FLOORS (limits enforced but never stated in templates) — the
   recurring failure class of this corpus: plan depth cap when extending
   deep namespaces (fix → 0.67), reflect plan_revision phase shape (fix →
   1.0), intervention trigger for contradictory sources + 25-word question
   cap (fix → 0.83). Same class found+fixed in both route prompts
   (reason ≤ 12 words). Rule for future prompt work: every `limits.py`
   validator a payload can trip must appear in its template's skeleton or
   Check line. Routing floors bootstrapped same day (reuse-over-create 1.0,
   warranted-new-leaf 0.8, goal-extend-not-duplicate 1.0) — pair baseline
   now 29 scenarios, mean **0.835**. Remaining owed: reflect weak
   categories (resolve/patterns) iteration; heartbeat-flow scenarios for
   wave 4.
5. ✓ v0.2.0 tagged + pushed 2026-07-09 (owner's default at the pause);
   v1.0.0 decision still reserved for after the quality-iteration work.
6. Backlog (ledgered in docs/design/usecase-audit.md + OPEN-PROBLEMS):
   OP #14 queue-limit archives consolidated memories; fulfilled-task
   housekeeping (tasks/ grows forever); interleave share tuning (wants real
   usage data); OP #13 snapshot-undo. (ADR 005 maintenance: shipped in
   item 3b.)

## Standing owner directives (must survive every session)

- No context bloat; token spend is the owner's money — budgets are tested.
- Model-strength neutrality: floor-not-ceiling (design/prompts.md §1b).
- Delete-over-retain: git is the archive (`archived_implementation/` exempt, Q4).
- Never lose directed work; strictly highest-value-first (method §3).
- Extract-never-enrich: the system learns the USER's words, not AI embellishment.
- README tracks only shipped+working features; keep it and this STATE current.
- Eval/benchmark: fulfiller-agnostic, per-(driver,judge) baselines, reproducible;
  codex is locally available for real runs — never hardcoded.
- Serious, VARIED corpus; benchmark results grouped by category for users.

## Session changelog (compressed; git log has the story)

- 07-07: design (blueprint, ADRs 010–016) → M0–M2 (store, task contract,
  prompts, evals T1/T2) → M3 (py-fsrs, packet, daily/why, boosts).
- 07-08: corpus waves 2–3 + interventions + coverage ratchets; benchmark CLI +
  token footprint; capture/inbox; SKILL rewrite; export/uninstall; M6 live E2E
  (caught day-one bombardment + diagnostic dead-loop); owner field reports fixed
  (packaged skill, venv detection, benchmark honesty, ensure_ascii judge bug).
- 07-08/09: interactive human CLI; use-case audit (10 fixes, daily-as-heartbeat);
  attempt-filename overwrite bug found+pinned. Baselines: compliance 1.0,
  quality 0.732 (pre-rebaseline).
- 07-09 (docs session): ProperDocs+mkdocstrings site (`mise run docs`); 100%
  docstring coverage + gate (257 tests); README audit; change-authority +
  `dojo more` designs ledgered in QUESTIONS; task-run Q confirmed shipped.
- 07-09 (authority session): change authority shipped (rails+prompt+corpus,
  283 tests); items 1–3 designs finalized with owner (at-request `more`,
  final completion-message copy, streak→stats, route-first, ownership
  block); delegation/model-economy rules added to the METHOD repo (§4).
- 07-09 (learn session): route-first entry shipped (`dojo learn` +
  goal.route kind + extend|new consent verbs + learn_flow; 306 tests);
  STATE item 1 closed. Same session: capacity channel shipped (`dojo more`
  + debt guard + origin markers + spec'd completion copy; 325 tests);
  STATE item 2 closed. Same session: ownership block shipped (insights
  see/trace/contest + stamping; campaign list/archive, completion →
  maintenance, windowed criteria, idle notices; 344 tests); item 3 closed.
