# STATE

_Last updated: 2026-07-09 late (field-bug + first-holdout-gate + Anki-investigation
session). Trust this snapshot; git history carries the detail._

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
with deterministic completion → ADR 005 maintenance), **provenance traces**
(every submission verbatim on its task; `task show --trace`), **task
housekeeping**, and the **anti-reward-hacking eval program** (55-scenario
visible corpus + 19-scenario blind holdout with structural isolation).
**522 tests green** + eval-marked tiers.
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
baselines over a 55-scenario judged corpus + compliance corpus + golden
payload/footprint pins, with a 19-scenario BLIND holdout (aggregate-gap-only,
release gates) guarding against prompt overfitting.

## HOLDOUT GATE — first live run (2026-07-09, owner-authorized)

**Verdict: gap 0.184 (visible 0.833 over 55 · holdout 0.649 over 19) — above
the ≤ 0.1 healthy line, below the 0.2 overfit line. v1.0.0 NOT tagged.**
18/19 scenarios bootstrapped floors; `beaten_insight_resolution` scored 0.0
TWICE (bootstrap + one flake-check re-run) — a real failure, not noise. It
stays floorless until the insight-resolution skill improves on the VISIBLE
corpus (its name is the only signal consumed; content unread, protocol
intact). Floors-only holdout mean 0.685 → gap 0.148; including the zero,
0.649 → gap 0.184. Either reading: above 0.1, below 0.2. Gate mechanics hardened same day: refused zeros can never
persist as floors, later gates bootstrap unknown scenarios into an existing
baseline (burn-and-replace now works), floors never rewritten
(`merge_holdout_baseline`, unit-tested free-tier).
**Path to v1.0.0: the Q4 weak-floor iteration session (visible corpus only)
— language floors, diagnostic-kind prompt (never iterated), insight-
resolution reflect skill — then re-run the gate.**

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
   now 29 scenarios, mean **0.835**. Reflect weak-category iteration DONE
   same day (owner-authorized codex, spent sparingly: trace-driven analysis
   first, 11 scenario-runs total): rows now compile topic · seconds ·
   error_tag · 48-char answer glimpse (the doc promised them; patterns were
   structurally invisible), per-insight adjudication, strategy enums stated,
   rushing carve-out (fast-miss/slow-success ≠ difficulty problem). Floors:
   mastery_resolution 0.38→1.00, too_hard 0.57→1.00, too_easy 0.56→1.00,
   plateau 0.50→0.62, overconfident 0.50→0.62 — pair mean **0.895**.
   Reflect payload 2523→4198B (deliberate: the rows now carry the evidence
   reflection exists to read). Remaining owed: heartbeat-flow scenarios for
   wave 4.
6b. ✓ **DONE 2026-07-09 (late session) — anti-reward-hacking program**
   (owner directives, all shipped): HOLDOUT tier final at 19 skill-named
   scenarios (capped < visible per owner; authored BLIND via a codex
   pipeline + failure-mode audit; lead never read them), structural
   isolation (aggregate-only runner + benchmark --holdout with computed
   gap verdict; forbidden data never persisted; commands in CLAUDE_START),
   holdout floor bootstrap DEFERRED to the v1.0.0 release gate (first run
   = bootstrap + gate, one spend). Visible corpus enriched to 41 (12
   robustness scenarios incl. grading manipulation/verbosity/unicode,
   mixed signals, language policy) with 10/12 bootstrapped at 1.00; +12
   more visible scenarios in flight (diagnostic-kind first coverage,
   pending-grade integrity, band discipline, learner-language probes,
   change-authority voice, multicampaign registry, crosslang routing,
   downward calibration). Learner-language policy shipped (identifiers/
   templates English; learner-facing text follows the learner). Task
   housekeeping shipped (spent unreferenced tasks age out via daily;
   provenance untouchable). Codex spend policy + holdout-never-optimizes
   rulings in memory + CLAUDE_START + here (standing directives).
5. ✓ v0.2.0 tagged + pushed 2026-07-09 (owner's default at the pause);
   v1.0.0 decision still reserved for after the quality-iteration work.
5b. ✓ **DONE 2026-07-09 — provenance traces** (owner-directed, design in
   QUESTIONS): every submission persists verbatim on its Task (tail-clipped,
   accepted AND rejected; `dojo task show <id> --trace`); `Attempt.grade_run`
   closes the last pointer; `insights show` walks belief → answers → task →
   the model's own words. Eval reports now carry `driver_trace` beside
   ratchet scores (baselines stay lean via `lean_baseline`) — reflect-prompt
   iteration (the remaining owed work) now has the model's thinking to read.
   Also same session: validator caps interpolate from `limits.TEMPLATE_CAPS`
   (owner-agreed; drift gates in test_prompts.py); reflect plan revisions
   can't strand ghost topics (registry shown, paths validated, scheduled ⇒
   registered).
7. ✓ **DONE 2026-07-10 — ADR 017 encoding stage & practice continuity**
   (all units shipped: 79d158f substrate+gap, cd68889 present+history window,
   7a4fdd2 retirement+trends+question rule, plus SKILL/corpus commit).
   Owner rulings binding forever: noise is the test at every juncture; every
   pedagogy surface benchmarked; task contract stays single-shot (tool-call
   enrichment REJECTED — see ADR 017); prompt sections stable-prefix-first.
   Visible corpus 55→61 (new categories: encoding ×2, care-exit ×2,
   grading-integrity 6→8) with coverage floors ratcheted. **Quality floors
   for the new scenarios are UNBOOTSTRAPPED** — they bootstrap on the next
   owner-authorized real eval run (`-m eval`, codex spend policy applies).
7c. **IN FLIGHT 2026-07-10 — visible-corpus eval run (owner-authorized codex
   spend)** for post-ADR-017 re-baseline + 6 new floors. Triage mandate
   (owner directive, same day): TWO axes — (1) quality regressions vs the
   0.895 pair baseline, weak floors iterated visible-only; (2) **output
   token length**: audit response_bytes per task kind + driver traces for
   verbosity (reasoning preambles, cap-padded answers); tighten output
   contracts/word caps where fat — users' token budgets are the product's
   money. Then the owed tag-blocking floors (insight-resolution skill,
   diagnostic-kind prompt, language floors). Tag bar: holdout gap ≤ 0.1
   STRICT. VISIBLE CORPUS ONLY — holdout stays sealed (see 7b).
7d. **DIRECTED 2026-07-11 (owner; investigation before design):** the
   reflect mega-task is an ANTI-PATTERN — one call now juggles five jobs
   (insight adjudication, strategy dials, plan revision, questions, topic
   retirement), and multi-sample eval variance (different criterion dropped
   each run) is the measurable symptom. Investigate decomposing AI tasks
   into straightforward single-job calls: candidate shapes (split reflect
   into adjudicate/calibrate/govern passes? conditional sub-tasks emitted
   only when evidence warrants? two-stage triage→act?), weighed against
   token cost (N small calls vs 1 big), latency, weak-model benefit
   (single jobs are the model-strength-neutrality win), and applier/
   authority complexity. Deliverable: investigation + proposal for owner
   gate — not implementation.
7b. **NEXT (OWNER PROTOCOL — subagent with cold context, this or any session):
   holdout enrichment for the ADR 017 surfaces.** Owner ruling 2026-07-10:
   prompts FIRST (done, this session), THEN holdout, and the session that
   authors holdout scenarios must NEVER touch prompts afterward — start a
   NEW Claude Code session whose only job is: read ADR 017 + public
   contracts (schemas/limits; NOT the visible corpus, NOT this session's
   scenarios), author ~5-6 holdout scenarios covering the same skill
   breadth (encoding, care-exit, gap-grading incl. adversarial,
   history-use) into src/dojo/evals/corpus/holdout/, run the shape suite,
   commit. Holdout stays smaller than visible; floors bootstrap at the
   v1.0.0 release gate as already planned. NEVER optimize prompts on
   holdout data — one aggregate bit per gate run, unchanged.
8. ✓ **DONE 2026-07-10 — vault-grade store layout (ADR 018, commit 0ab991f)**:
   investigation first (owner precondition) — no surface reads the journal's
   full-text snapshots; only plan-authority snapshots are functional. Campaign
   aggregate → five files (campaign.md scalars+syllabus · plan.yaml ·
   topics.yaml · .journal.yaml machine log · journal.md prose projection);
   dead snapshot fields stripped at writers + historically on save; doctor
   migrates legacy stores in one pass (verified against a copy of the
   owner's live store: campaign.md 12.4KB → 2.1KB, 87% → ~15% frontmatter).
   Owner's real store migrates on his next doctor/install run.
   DEFERRED phase 2 (ledgered): Obsidian wikilinks between entity files
   (needs id↔filename harmonization).
6. Backlog (ledgered in docs/design/usecase-audit.md + OPEN-PROBLEMS):
   fulfilled-task housekeeping (tasks/ grows forever — now including
   submission traces, so the cleanup pays for provenance too); interleave
   share tuning (wants real usage data); OP #13 snapshot-undo. (ADR 005
   maintenance: shipped in item 3b; OP #14: fixed 2026-07-09.)

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
- **NEVER optimize prompts on holdout-set data** (absolute, 2026-07-09):
  one consumable bit per holdout run (aggregate gap); bad gap → broaden the
  visible corpus, iterate there. Applies to every contributor, human or AI.

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
- 07-09 (field-bug/gate session): owner live-drove `dojo learn` — five field
  fixes shipped: store index skipped the ENTIRE store when its path holds a
  hidden component (~/.local/share default was 100% invisible; every get →
  None; 3999d2d), `uninstall --self` now truly removes venv/launcher with
  plan/execute split + human confirm flow (b189d42), readline line editing
  + refinement-question separation (044546b), doctor advisory-vs-structural
  split (a mid-command dirty store no longer aborts+ROLLS BACK installs) +
  new Installation integrity category + in-process template snapshot
  (conversations survive install replacement) (db666ba). First holdout gate
  run (see section above): gap 0.184, no v1.0.0, ratchet writer hardened.
  Anki interop investigation delivered (docs/design/anki-interop.md; PM +
  engineering; QUESTIONS Q2 updated) — headline: scoped import/export ideal,
  FSRS-native transfer is the differentiator, sync stays rejected.
