# STATE

_Last updated: 2026-07-17 (learn ride-along field session). Trust this
snapshot; git history carries the detail._

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
Repo is PUBLIC (owner confirmed 2026-07-18); docs site auto-deploys to
https://stan15.github.io/dojo/ on main pushes; owner's machine runs the
current build via checkout `sh install.sh`.

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
7c. ✓ **DONE 2026-07-11 — post-ADR-017 visible corpus HEALED** (full run
   0.799 mean → trace-driven triage → 5 fix commits → all 61 scenarios pass
   floors). Root causes found+fixed: present-move over-application (rules
   1b/1c rails), RECENT topic-scoping collapsed cross-topic struggle signal
   ("struggle travels, success aggregates" rows), retirement-channel misuse
   (TRENDS-listed-only rule), floundering both-dials ambiguity, scaffolding
   never defined as item design, verbatim-stays-verbatim, judge
   escape-decoding bug (LaTeX evidence discarded — evidence_haystacks fix
   + free tests), route seed honesty. Token audit: plan responses fattest →
   PlanTopic.summary word-capped (18); phase numbers no longer emitted by
   models (position-assigned). Output anchor now REASONING-NEUTRAL (owner:
   never invite, never suppress). Two floors adjusted on multi-sample
   evidence (owner-approved; notes in the baseline card). **PROMPTS FROZEN
   at d2d024f for this era** — next prompt work belongs to a fresh session
   (see 7e). Also shipped: `benchmark.judge` standing-judge config +
   honest compliance banner (5f02c89); owner's store configured with codex
   as standing judge. Weak-model program: qwen3:4b + gemma3:1b +
   LFM2.5-1.2B pulled; owner drives the bake-off via the benchmark TUI
   (compliance first — free; judged tiers on finalists).
7e. **CONTAMINATION EVENT 2026-07-11 (recorded per the CLAUDE_START rule,
   same day):** an IDE selection accidentally relayed partial holdout seed
   content (reflect_retirement_not_phase_prize.yaml, ~8 attempt rows) into
   the working session's context AFTER the prompt freeze (d2d024f). Per
   protocol: that session is permanently disqualified from prompt work; no
   prompt work was pending (freeze predates the leak); item 7d MUST be
   executed by a fresh session. Non-prompt work (benchmark runs, gate,
   relaying blind-subagent reports) unaffected.
7f. ✓ **DONE 2026-07-17 — generated campaign names + ride-alongs shipped**
   per the owner-reviewed design below: PlanResult requires `name`
   (≤ ROUTE_NEW_NAME_WORDS via TEMPLATE_CAPS placeholder), payload lists
   existing campaign names (SECTION_BUDGETS +300B), template rule 6b +
   skeleton + Check line, proposal panel titles with the name, materialize
   prefers it (raw goal only as fallback), `dojo campaign rename` (display
   name only, collision-refusing), learn-extend hint distinguishes
   already-active (topic-boost) from scheduled-later (start --topic).
   Visible plan references gained exemplar names; the three HOLDOUT plan
   scenarios were name-patched by a cold-context subagent under the blind
   protocol (filenames-only report; this session read nothing). Plan
   footprint 2540→2848 (deliberate). Owner must `sh install.sh` to get it.
   _Original directive:_ `dojo learn "<long goal>"` currently makes
   the raw goal the campaign name+id (owner's store: camp_i-have-terrible-
   memory). Design (owner-reviewed in conversation): PlanResult gains
   `name` (≤ ROUTE_NEW_NAME_WORDS=4, same cap as route new_name), one
   payload line lists existing campaign names (prevention), template
   states the cap; shown in the proposal panel for approval. The
   deterministic COLLISION FLOOR (id/display suffixing across all creation
   doors, archived ids count as taken) is code and shipped (cff9966).
   Goal text stays verbatim in mission — the name is a label, labels are
   AI work. Ride-alongs for the same block (owner field flow 2026-07-15):
   (a) `learn extend`'s already-in-plan hint must distinguish "scheduled,
   LATER phase" (right door: `dojo start --topic <path>` — topic-boost is
   phase-gated and does nothing until that phase activates) from "already
   active" (topic-boost is correct); (b) `dojo campaign rename <id>
   "<name>"` so existing paragraph-named campaigns can be fixed in place.
7g. ✓ **DONE 2026-07-17 — learn ride-along field batch** (owner live-drove
   `dojo learn "how to cook"`; six reports, six fixes, commit 963b7ed):
   plan-template rule 3 stated phase-1 criteria without min_accuracy
   (the invisible-floor class again — field crash); calibration is now
   UNGATED BY INVARIANT (owner ruling: calibration measures, never gates
   — template states min_accuracy 0, PlanResult validator enforces it at
   the boundary; PlanRevision deliberately untouched; authority rails
   make it one-way). First-practice chain healed: materialize stamps
   diagnostic mode (parity with direct door), start treats no-evidence
   campaigns as calibrating (packet rule mirrored), advancement past
   phase 1 clears the stamp (LATENT: nothing ever cleared it — direct-
   door campaigns replenished diagnostics forever), warm start
   replenishment auto-promotes (daily J1 parity — candidates starved the
   session that asked). drain_tasks spends the full submission budget +
   human-readable errors + next steps. Refinement '/back'. Copy fixes.
   696 tests green (14 new); plan footprint 2407→2540 (deliberate).
7h. **DIRECTED 2026-07-17 (owner; design for gate — QUESTIONS 6c):**
   SKILL.md behavioral evals — the driver-side prompt surface has zero
   behavioral testing. Design delivered:
   `docs/design/skill-behavioral-evals.md` (`-m eval_skill` tier, ~6
   real-world sandboxed agent scenarios, deterministic floor free +
   judged rubric under spend policy, ratcheted per-(driver,judge)).
   Nothing built until gated.
7d. ✓ **INVESTIGATION DELIVERED (found uncommitted in-tree, committed
   0610a03 on 2026-07-17): `docs/design/reflect-decomposition.md` +
   QUESTIONS 6b — awaiting the owner gate; nothing built.** Original
   directive: the
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
7b′. ✓ **DONE 2026-07-11 — holdout enriched to 24 scenarios** by a
   cold-context subagent under the CLAUDE_START blind protocol (350b4e2;
   one scenario burnt + regenerated after an accidental partial exposure,
   18d83dc — leak permanently neutralized). Filenames-only reporting held;
   mechanical QA green. Floors bootstrap at the v1.0.0 gate as planned.
   _Original protocol text kept below for the next enrichment:_
7b. **(protocol reference — subagent with cold context, this or any session):
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

9. **CAMPAIGN COMPLETE — AWAITING OWNER MERGE GATE (dev/token-diet,
   2026-07-18): token-diet.** Winner `armJ5S` shipped on-branch, 722 tests
   green [MERGED to main 03402c4 on 2026-07-18 — verified in git by the
   2026-07-18 late session; this entry's "awaiting merge gate" is history]:
   shape-hardened templates + semantic-only validation + permanent
   bidirectional gates (shape-lints, semantic-validation tests, prompts.md
   rule 7 + §1c, guard README chain). Results: class-verdict qwen3.5:4b
   26.3±3.2 → 33-35/64 with 5× variance collapse; gemma3:4b 28 → 50-53;
   lfm 11 → 21; floors unchanged; judged quality parity; skill-bleed found
   and de-anchored. **Full story: `scratch/token-diet/REPORT.md`;
   continuation detail: WORKBENCH.md same dir.** Accumulate-batch of
   deferred marginal wins ledgered there. Merge to main is owner-gated.

10. **DONE 2026-07-18 — release-gate remedy iteration (fresh session;
   holdout blindness intact throughout).**
   a. Visible corpus 64→79, broadened EVENLY (every category +1; routing +2,
      planning +2; thinnest kinds lifted most: diagnostic 2→3, goal_route
      1→2, route 4→6, plan 7→9; opposite-branch controls for one-way-
      rewarded behaviors — propose-new / minimal-restructure / no-present /
      no-retirement-as-escape; +2 prose-feedback discernment scenarios from
      the owner's story — grade meta-feedback-in-answer, reflect
      confusion-is-item-signal). 15 fresh domains; floors ratcheted
      (aec60a2, f1bf792).
   b. Prompt iteration on VISIBLE evidence only (committed baseline weak
      floors + 2026-07-10/11 report verdicts; 43e4e48's three unmeasured
      fixes left alone): reflect [extension]-discount rule (binge 0.0×2 —
      marker shown, never defined) + voiced-scope-fidelity sentence;
      generate downward-calibration branch (0.3×2); plan 1-N phases
      sized-to-goal (template contradicted PLAN_MIN_PHASES=1; 0.44×2).
      Token gates re-established by real local re-measure over 79 scenarios:
      qwen3.5:4b every kind ok same-or-better; gemma3:4b 63/77 with reflect
      UP 11/20→17/22 and reflect bytes median DOWN 756→537; output-budget +
      footprint + golden updated same commit (cc654cc). 765 tests green.
   c. Owner-directed ride-alongs, all shipped+pushed: campaign-name
      propagation root fix (9c5abdd — apply_plan dropped PlanResult.name;
      every campaign fell back to the slugged goal), name-first UI surfaces
      (75f8f6c), README rebuilt per growth principles then cut to
      simplicity-first (30d5d2c; insights receipts shown with real output,
      no-guilt said aloud, capture-links validated live before claiming,
      measured small-model guidance), SKILL why-directed extraction
      (292a0e3), OPEN-PROBLEMS 16-18, QUESTIONS 6f (vault export) /
      6g (capture core-need: why→generation + planned-campaign-from-capture,
      owner-gated) / 6h (quit-as-evidence design).
   d. ✓ **Codex validation run DONE 2026-07-18 (owner-authorized)**: 77/83
      pass, mean 0.833→0.855; ratchets committed (643d9ec — 23 floors
      bootstrapped, 15 raised). The remedy iteration MEASURABLY landed:
      binge-discount 0.0→1.0, learner-language 0.1→0.8, single-fact-goal
      0.44→1.0; partial voice-revision 0.33→0.44; unmoved:
      downward-calibration 0.3, grade_learner_language 0.67, diagnostic
      pair ~0.6. **FIVE STABLE DROPS vs pre-iteration floors (failed BOTH
      samples; floors NOT lowered, multi-sample rule):**
      inferred_restructure_probe 0.89→0.67/0.67 · learning_loop_chain
      0.75→?/0.62 · mastery_resolution 1.0→?/0.88 · plan_extend_not_
      duplicate 0.67→?/— · reflect_mixed_signals 1.0→?/0.67 (sample-2
      verdict: difficulty moved when the rubric wants dials held — smells
      like the floundering-both-dials wording era, NOT diagnosed).
      verbatim_poetry_recall recovered (0.5→1.0, noise).
      present_before_probing scored 0 once — floorless, undiagnosed.
      Both runs' full traces are in evals/reports/ (local).
      **NEXT (fresh session with prompt authority — this one is
      disqualified, 10f): diagnose the five drops + the three unmoved weak
      floors from the traces, iterate on visible evidence, THEN the owner
      re-triggers the holdout release gate.**
   d2. **SKILL behavioral tier shipped (7551ad7; owner-approved), first
      REAL run still owed**: harness + 6 learner-speak workflow scenarios +
      deterministic checks + judge rubrics + `dojo benchmark --skill` are
      in, proven with scripted drivers only. Next spend (owner-authorized):
      pick a driver-agent command with shell access, run `-m eval_skill`
      once to smoke the battery and bootstrap deterministic floors; judged
      rubric floors ride the next authorized judge spend (design doc
      §Recommendation).
   e. The uncommitted `evals/baselines/*__holdout*.json` modification left
      by the disqualified gate session remains untouched and unread by this
      session — owner dispositions it (commit or discard).
   f. **CONTAMINATION EVENT 2026-07-18 (this session, late):** a harness
      change (shared seed_store gaining `sources` support for the new skill
      tier) broke holdout scenario execution in the DEFAULT suite, and
      TestCorpusIntegrity's name-bearing pytest ids printed failing holdout
      stems into this session's context (4 ids; 2 were read). Per the
      total-blindness ruling this session is now DISQUALIFIED from further
      fulfiller-template / visible-quality-corpus work (all such work above
      predates the leak). Remedied BLIND: seed_store reverted (source
      seeding moved into the skill harness), holdout integrity re-green
      without reading any content, and the vector closed — holdout ids are
      now opaque (`holdout_NN`) in the default suite. Driver-side skill
      tier, README, STATE, and mechanical ratchet bootstraps remain in
      scope; any further template/corpus iteration belongs to a fresh
      session.

   g. **2026-07-18 (late, separate session — non-prompt scope only; the
      drops-diagnosis session had NOT landed, so templates/visible corpus/
      baselines untouched): skill-tier hardening.**
      (i) Owner probe on respect_the_no ("there is a `more` pathway, no?")
      confirmed sharp: the seed carried ~3 dues vs capacity 28 — the debt
      guard would have GRANTED and only the no-material branch refused;
      a daily-first driver could be granted then punished by
      no_extension_session for walking the sanctioned door. Seed now
      guarantees the guard refusal (packet_size 2 via new skill-seed
      `configs` block — skill harness only, shared dialect frozen; 12 dues
      in-horizon vs capacity 11), premise pinned by a free test (7d8e283).
      (ii) Bootstrap-install scenario shipped (launch-prompt invitation;
      PATH isolation proved tractable): `fresh_machine` sandbox shadows
      PATH (minus dojo/pipx) and HOME (minus .dojo/.local — install.sh's
      rm -rf rollback can never reach the real install; agent auth passes
      through), new `dojo_binary_installed` check, battery now 7, free
      plumbing tests (1037b1c). Design-doc addendum + INSIGHTS entries
      committed. 805 tests green. First real `-m eval_skill` run still
      owed — blocked on the owner's driver-agent pick (10d2).

11. **IN PROGRESS — PROMPT LAB: autonomous quality-density campaign
   (owner grant 2026-07-19, standing).** The owner authorized continuous,
   uninterrupted prompt improvement: judged quality AND output-token
   efficiency (quality-density), all calibers, codex spend included;
   adopt only measured wins; NEVER reward hack; holdout blindness stays
   TOTAL and the release gate stays owner-triggered. **Directive (point
   any session at it): `docs/PROMPT_LAB.md`** — it self-arms a resilient
   heartbeat (STEP ZERO) and resumes from
   `scratch/prompt-lab/WORKBENCH.md` (live state: in-flight inventory,
   pre-registered hypotheses, results/negative-results, spend ledger).
   Completed within this campaign so far: drop-diagnosis of all 10d
   targets (judge multi-quote fix 3c3041f; template+compiler fixes
   pending their same-commit battery gate), P1 letter-bleed
   catch-and-fix, INSIGHTS 2026-07-18/19, QUESTIONS 6i/6j. This session
   entered via CLAUDE_START as STATE 10f's fresh session; its full
   handoff detail lives in the WORKBENCH, not here — STATE stays the
   map, WORKBENCH the territory.
   **Drop-diagnosis arc CLOSED 2026-07-19** (commits d69ff5c fb9fe04
   03d466d 9fb94e8 1ff6425): all five 10d drops + three unmoved floors
   recovered and codex-verified; the iteration's own regressions were
   caught by the campaign's pre-registered batteries and fixed in two
   further verified rounds (op-count anchoring, dial precedence+levels,
   scope anchor, path charset, skeleton self-consistency, mismatch
   branch, scaffold answer-leak). README reflect demo now measured on
   qwen3.5:4b (2/2 budgets). Whole-battery: qwen 42→47/79, gemma
   68/79 flat, zero letter-paths. Residual queue: P9 (descriptive
   placeholder id), P10 (kind-mix under deadline compression), then
   the standing experiment queue (6i traps first). Holdout gate:
   ready for the owner whenever they choose — drops dispositioned.

## RELEASE GATE STATUS (2026-07-18) + CONTAMINATION HANDOFF

The v1.0.0 holdout release gate was RUN (owner-approved) and FAILED — v1.0.0
tag WITHHELD. That fact is the only consumable output. The session that ran
it saw pytest's per-scenario failure ids (a leak since fixed: the gate is
now a single aggregate test, total-blindness assertion messages) and is
therefore DISQUALIFIED from prompt/corpus work. Remedy per protocol, for a
FRESH session only: broaden the VISIBLE corpus evenly across ALL categories
(no holdout-informed targeting is possible or permitted), iterate prompts
on visible evidence under the token-shape gates, then owner re-triggers the
release gate. Holdout blindness is TOTAL (owner ruling 2026-07-18): names,
counts, scores, files under corpus/holdout/, evals/baselines/*__holdout*,
evals/reports/holdout-* — all off-limits to any prompt-work context.

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
- Delegate to cheaper models where quality is provably unaffected
  (owner, 2026-07-18): mechanical script execution, verifiable-number
  aggregation, reviewed docs drafting. Never: prompt-template wording,
  decision verdicts, unreviewed merge-destined code.
- Weak-model benchmark calibers = the BEST model of each resource class
  (2026-07-17): local users run the strongest model their hardware allows, so
  an arbitrary same-footprint pick misstates the real-world floor. Class
  verdicts come from the best-in-class (2026-07: qwen3.5:0.8b ~1GB,
  qwen3.5:4b ~3.4GB); weaker same-class models are robustness points only.
- **Prompt work and token work are mutually non-regressing, and BOTH
  directions are tested** (owner, 2026-07-17): every future prompt/quality
  optimization must preserve token-diet gains (output-shape discipline,
  rejection-retry elimination, thinking-cost awareness), and every token
  optimization must preserve quality — each side runs the other side's
  gates. Quality direction: corpus floors + ratcheted eval baselines +
  release-gate holdout (exist today). Token direction: static template
  shape-lints (weak-model-hostile patterns) in the default gate + ratcheted
  output-bytes-per-successful-task baselines for real-model runs — landing
  with the token-diet winner commit (dev/token-diet; see WORKBENCH step 5).
  A change that wins on one axis by losing the other is a regression, full
  stop.
- **NEVER optimize prompts on holdout-set data** (absolute, 2026-07-09;
  TIGHTENED 2026-07-18: blindness is TOTAL — names and counts included,
  not just content; the gate emits pass/fail + aggregate gap and nothing
  else). One consumable bit per run; bad gap → broaden the visible corpus,
  iterate there. Applies to every contributor, human or AI.

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
- 07-17 (learn ride-along): owner live-drove `dojo learn` — six field
  reports → 963b7ed (ungated-calibration invariant, first-practice chain,
  submission-budget retries + honest failure copy, '/back', copy fixes;
  14 new tests). Prior session's reflect-decomposition deliverable found
  uncommitted → 0610a03. SKILL.md behavioral evals designed for gate
  (7h / QUESTIONS 6c). INSIGHTS: partial-statement subtype of the
  invisible-floor class; stamps need clearing edges; spend granted budgets.
- 07-17 (second wave, same owner drive): 7f generated-names shipped (see
  7f) + calibration command/junk discipline (unknown slash-commands and
  /exit never submit; junk refused unrecorded; "noted" not "correct";
  /back counter uses authoritative index — was marching to "5 of 2"),
  confirm() '[y/N]' rich-markup swallow fixed, display flags app-wide
  (QUESTIONS 6d; conversational-surface screen unification + in-place
  live-region hybrid ledgered there), junk-detection depth ledgered
  (QUESTIONS 6e), '/back' at the amend review chains further back (was
  cycling), more's open-session refusal speaks human at a TTY
  (alternative_interactive: dojo daily, never the agent envelope).
  706 tests green.
- 07-19 (prompt-lab, W1): OWNER RULING implemented — word caps are strong
  suggestions: validators reject only past ceil(cap × WORD_CAP_TOLERANCE=1.5)
  (limits.word_cap_hard, single source; _cap_words family + 3 question
  validators + diagnostic prompt check), teaching rejection messages name
  actual count + suggested cap; templates still state the tight cap (anchor
  and gate now do different jobs). Mini-batteries: gemma plan 13/13 (was
  9/11 — question-cap class fully converted), qwen plan +2, gemma reflect
  +1, qwen reflect neutral (churn root-caused to the cross-caliber
  questions-object format lottery — W2 coercion pre-registered, 119 archive
  hits sized). Output-budget rebuilt (w1cap splices). Realworld batteries
  adjudicated: qwen 7/12, gemma 8/12, no new classes. Sub-4B bake-off slate
  researched+pulled (qwen3.5:2b, granite4:1b, lfm2.5-thinking:1.2b);
  bakeoff_run.sh staged. 926 tests green.
- 07-19 (prompt-lab, bake-off + W2/W3): sub-4B class verdict REWRITTEN by
  7-model bake-off under W1 tree — lfm2.5-thinking:1.2b takes the ~1GB tier
  at 51/104 single-shot (old rep qwen3.5:0.8b: 10/104); README re-based;
  family non-uniformity + per-kind divergence ledgered in INSIGHTS. W2
  landed (questions object→string coercion, cross-caliber, class-kill
  confirmed 0 hits in confirmation battery); W3 landed (evidence decoration
  strip; latent empty-evidence bypass closed). W5 core-rescue + W2b type
  coercion sized and closed NEGATIVE (W3 captured the recoverable mass;
  type pool is old-era degenerate output). Verbatim-check taxonomy for the
  owner: 79% ungrounded / 17% near-miss / 4% answer-key catches — strict +
  W3 recommended equilibrium. Owner proposals drafted (reflect-decomp
  closing evidence; per-kind mixed-model routing). R3-LFM retry probe in
  flight. 937 tests green.
- 07-19 (prompt-lab, session close-out wave): R3-LFM retry-feedback probe
  NEGATIVE by pre-registration (+13 vs +15 bar; interim +36 was a
  sampling-order artifact — feedback rescues verbatim-evidence 5/7,
  field-omission 0/12; fourth and final R3 negative). W4 enum-phrasing
  NEGATIVE and reverted (rumination migrated to the next informal
  descriptor; root cause = deliberation-budget exhaustion on rule-dense
  route payloads — thinking-class simplification profile queued).
  EX-BLEED ADOPTED (871db97): content-orthogonal reflect example values —
  bleed 16→8/27 gemma (ok 27→29/30, best measured), 9→2/27 qwen
  (replicated), README-mode-9 refinement ledgered in INSIGHTS. W1
  verbosity guard closed (codex: 3 SUBSTANTIVE / 1 PADDED on a 4-field
  tail). W2/W3 judged debts closed by content-preservation argument.
  BLOG_MATERIAL.md dossier established + wired into the loop (capture-
  first standing directive). 937 tests green; all raw data committed.
- 07-19 (prompt-lab, EXB2): create-example suppression on the with-insights
  reflect path ADOPTED (e3e3504) — create-bleed 0/0 both models on the
  target path, create-fails down (the feared shape-anchor loss never
  materialized), ok flat. Ledger holds the full honest arc: as-written
  rule FAILED on a mis-scoped bar → mechanical path-attribution proved the
  mis-scoping → corrected rule pre-committed before the second model's
  data → adopted under it. Second load-starvation void handled by a
  load-gated fill watcher (11 timeouts at system load 60, reran at <6).
- 07-19 (prompt-lab, route arc): W4/RSIMP/RFIX/RFIX2 route arms adjudicated
  in one evening — lfm-think route confirmed capability-floor (0/13 under
  three surgeries); the three-sided skeleton trap measured (see INSIGHTS);
  RFIX3 landed: fulfiller.route_skeleton profile — default legacy-null
  byte-identical, opt-in "live" interpolates the learner's real registry
  (qwen route 1/8 → 12/13, campaign-largest cell win). RSIMP lean-route
  profile infra in tree (opt-in, unused, gemma spot 6/6). 943 tests green.
- 07-20 (prompt-lab, owner-approved pilot + follow-ups): codex validation
  run adjudicated (96/108; 5 variance / 7 reliable fails, none causally
  traceable to the day's adopted arms — EXB3 parked, holdout relay stays
  parked per the owner's green-run condition). REFLECT-DECOMP PILOT ran
  (approved 07-20): the ops/voice split ELIMINATED journal-omission at all
  three models but missed its acceptance bar (qwen 15/30 vs ≥18; per-op
  composition moved into call 1) — not adopted, infra opt-in, QUESTIONS −3
  answered by measurement. That diagnosis produced DOPS: per-op field-rule
  geometry landed as fulfiller.reflect_field_rules (gemma 29/30
  campaign-best, op-composition fails 0; qwen worse twice → profile, not
  default). Third measured instance of caliber-divergence (INSIGHTS).
  FINDINGS.md per-template register created + drift-gated; README carries
  every win/dead-end for future editors. 952 tests green.
- 07-20 (MAINT adopted, owner ruling): the raise-difficulty rule gains its
  maintenance guard ("on ACTIVE practice, not maintenance reviews of a
  passed phase") — adopted on shape evidence after a plain-language owner
  exchange (qwen 18/30 campaign-best reflect; gemma in-band; the stricter
  judged gate recorded as unmeasured-not-failed since its key scenario is
  bimodal below n=5). The owner's two challenges today — the over-tight
  gate-1 bar and "are we losing wins?" — each preserved a real win the
  process would have discarded. 12 adopted arms; 952 tests green.
- 07-22/23 (prompt-lab, hard-set phase): owner ruled green = noise-only
  fails; hard set 9→7 — gen_collision_sql cleared (seed↔rubric
  contradiction fixed, 1.00/0.80) and route_new_leaf cleared at 1.00/1.00
  via two single-variable arms (ROUTE-CHARSET #13: store-wide path
  validator + stated leaf format; ROUTE-REASON #14: reason names the
  coverage gap). VERB-RECALL mid-gate at session handoff (WORKBENCH
  RESUME header has exact resumption); DIAGVOICE pre-registered;
  restraint parked pending an n≥5 sampling budget. 14 adopted arms
  total; 952 tests green.
