# QUESTIONS for the product owner

Non-blocking. Each open question has the default I will proceed on if unanswered.

## PROGRESS BOARD (method §7) — owner-directed work, status per item

_Statuses: `[x]` shipped · `[~]` standing/in-progress · `[?]` blocked-on-owner ·
`[ ]` queued (fresh session). Updated 2026-07-18 session end._

- [x] Release-gate remedy: corpus 64→79 even + 4 prompt fixes + validation
      run (3 fixes measurably landed; mean 0.833→0.855). aec60a2…643d9ec.
- [x] Name-leak field fixes (applier root cause + all UI surfaces) · capture
      core-need (why→extraction→generation→plan chain, 6g) · OP #16-18.
- [x] README, all directives: growth restructure, receipts headlined with
      real model-tagged output, no-guilt, capture transcript, small-model
      guidance + gemma grade showcase, what-dojo-is-not, two-axes benchmark
      in plain words, hermes framing, prereq line, 100%-truthful examples.
- [x] SKILL behavioral tier (learner-speak workflows, personas, outcome
      checks + judge rubrics) + `dojo benchmark --skill` isolation.
- [~] **Weak-model insights demo for the README** (your ask: "even better
      if weak models produce the demo insights" — under the honest-trials
      bound). Attempted: qwen3.5:4b and gemma3:4b each got two full
      production task budgets on the demo scenario; all 12 single-shots
      failed on JSON shape (content was often right). Demo stayed gpt-5.5
      per your fallback. **REOPENS when reflect improves for weak models —
      first candidate: the empty-INSIGHTS skeleton fix (INSIGHTS
      2026-07-18: compiler leads with the create-op example when the store
      has zero insights). After any such fix lands: retry within the same
      bound (≤2 budgets/model), and if a 4B lands it, swap/augment the
      README demo with its exact model tag.**
      NOTES:
- [x] Fresh session (prompt authority) — DONE 2026-07-19 under the
      PROMPT_LAB grant (STATE item 11): all 5 stable drops + 3 unmoved
      floors + present_before_probing diagnosed from traces and FIXED at
      template/compiler/judge level (never scenario-specific); judge
      multi-quote fix 3c3041f; template commits d69ff5c, 9fb94e8,
      1ff6425; route-bleed scenario fb9fe04. Codex validation run + two
      targeted adjudications: 7 of the 11 post-iteration drops
      fixed+verified, 4 variance-confirmed, residuals P9/P10 queued in
      the WORKBENCH. Local batteries re-measured each commit; output
      budgets rebuilt same commit. README weak-model demo RESOLVED:
      qwen3.5:4b landed content-good reflects 2/2 budgets; README demo
      updated with the tag (03d466d).
- [?] Holdout release gate re-trigger (you; drops now dispositioned —
      gate is yours whenever you choose) · uncommitted __holdout
      baseline disposition (you).
- [x] Skill battery hardening (2026-07-18 late): your respect_the_no probe
      confirmed — seed now GUARANTEES the debt-guard refusal (`dojo more`
      is the sanctioned door; premise pinned by a free test, 7d8e283) +
      bootstrap-install fresh-machine scenario shipped (battery 7,
      shadow-PATH/HOME sandbox, 1037b1c). 805 tests green.
- [?] First real `-m eval_skill` run — needs your driver-agent command
      pick (STATE 10d2); battery is now 7 incl. bootstrap-install (that one
      needs network + main pushed current). · Docs hosting workflow on your
      word / go-public (Q 3b). · Gated designs: 6b reflect decomposition,
      6d display unification, 6f vault export, 6h quit-as-evidence.
      · NEW: 8 standalone binary / non-dev barrier (assessment delivered,
      defaults stated).

## Open — decisions actually waiting on you

-3. **Reflect decomposition pilot (2026-07-19, prompt-lab).** STATE 7d
   now has closing evidence: after W1+W2+W3 landed, the reflect residual
   at every measured model is journal-omission + op-requirement
   composition — the 5-job single call itself; identical failure classes
   across three model families; a controlled section-ordering probe (SORD,
   07-20) also measured NULL on the omission class — every non-decomp lever
   is now exhausted (full case:
   scratch/prompt-lab/draft_owner_proposals.md §1). Ask: approve a
   two-call decomposition PILOT behind a compiler profile, measured
   against the single call in one battery cycle. **Default: pilot it —
   measurement-only, no default change; the proposal dies on its own
   numbers if the token cost outweighs acceptance gains.**

-2. **Per-kind mixed-model routing table (2026-07-19, prompt-lab).** The
   bake-off's per-kind divergence makes a routing table a real product
   option for ~1GB learners (plan/diag on lfm-thinking, route on
   lfm-instruct, grade/reflect on a bigger tier); the fulfiller-profile
   machinery already branches per kind, and the new
   fulfiller.route_skeleton="live" profile (qwen route 1/8→12/13) shows
   the per-model win pattern concretely (full case: draft_owner_proposals.md
   §2). Ask: is a per-kind model table (store config + CLI surface) worth
   a design slot? **Default: park until a real mixed-deployment user
   exists; the profiles land per-kind wins without new config surface.**

-1. **Retry-feedback enrichment — CLOSED NEGATIVE, FYI only
   (2026-07-19).** Four R3 probes (qwen 4B ×2 cells, 0.8b, lfm-think)
   all failed pre-registered bars; the drafted proposal was retired
   (draft_questions_retry_enrichment.md holds the record). One narrow
   grade-only hypothesis stays parked pending a fresh pre-registered
   replication. **No decision needed; recorded so the idea isn't
   re-litigated from scratch.**

0. **Token-diet: 4-scenario codex bootstrap recheck (2026-07-18).** The
   authorized eval run passed 64/64 baselined scenarios but four newer
   scenarios (no committed floor for this driver pair) scored ZERO —
   two look example-bleed-related and armJ4 targets exactly that. To
   bootstrap their floors and confirm the fix at the strong tier, one
   4-scenario codex mini-run (~8 calls) is needed after armJ4 verifies
   locally. **Default: run it once armJ4S passes the local trio; it is
   the same-commit ratchet-bootstrap the eval protocol already expects.**

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
   listed in the doc §8. **The sync question you pressed is now §9 of that
   doc**: the SATELLITE model — dojo keeps sole scheduling authority, Anki
   becomes a rendering device (content+due dates push out; revlog outcomes
   flow back as origin:"anki" attempts that feed dojo's FSRS and the
   evidence loop). It engages §4's rejections directly (it is neither
   rejected shape) and challenges A2's binary-custody rule (custody-export
   amputates the evidence loop for phone reviewers; the satellite keeps
   them). Recommendation: A1 import first, then A2 defaulting to satellite
   with --handoff as the explicit exit; ADR 017 amends 015 to "no
   SYMMETRIC sync". **Default: parked until you promote it.**
3. **Repo visibility** → **PUBLIC (you, confirmed 2026-07-18).** The README
   curl one-liner and the skill's bootstrap line are now live paths;
   private-era fallback language removed from the skill.
3b. **Docs hosting** → **DONE 2026-07-18** per the recorded default, on
   your #3 flip: Pages enabled (build_type=workflow, via gh api),
   .github/workflows/docs.yml builds ProperDocs on every main push, site at
   https://stan15.github.io/dojo/ (README links it; mkdocs site_url set).
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
6b. **Reflect decomposition (STATE 7d)** — investigation delivered:
   `docs/design/reflect-decomposition.md`. Headline: the five-job reflect
   mega-task violates our own craft rule 5 (branching in the compiler, never
   the model); the measured symptom is multi-sample variance (a different
   criterion dropped each run) and a rule set at its byte ceiling. Proposal:
   compiler-decided conditional sub-tasks — `reflect.adjudicate` always
   (cheaper than today on quiet days), `reflect.govern` only when
   deterministic triggers fire; authority rails unchanged; typical-week
   tokens DROP ~15%. Costs priced in the doc: corpus migration, holdout
   re-enrichment (reflect-targeting holdout scenarios burn), cycle
   semantics. Recommendation: tag v1.0.0 on the current shape first; land
   decomposition as the first post-1.0 milestone, evidence-gated by a
   two-scenario spike. **Default: nothing built until you gate it.**
6c. **SKILL.md behavioral evals (your directive 2026-07-17)** — design
   delivered: `docs/design/skill-behavioral-evals.md`. Headline: SKILL.md
   is the highest-leverage prompt in the repo and the only one with zero
   behavioral testing (static gates only; every eval tier tests the
   fulfiller side, none the driver side). Proposal: `-m eval_skill` tier —
   ~6 real-world scenarios (learn e2e, daily ritual, capture, task
   protocol, failure recovery, refusal honesty), sandboxed store, driver
   agent given SKILL.md + a user message + a shell; two-layer judgment
   (deterministic store/transcript assertions FREE on every run; judged
   rubric under the codex spend policy); per-(driver,judge) ratcheted
   floors, same mechanics as the quality corpus. Holdout deferred until
   the surface stabilizes. **Default: nothing built until you gate it.**
6d. **Display-system unification (your directives 2026-07-17)** — shipped
   now: --screen/--transcript are an app-wide flag pair (shared parser
   parent) on every practice-bearing command (daily, more, learn,
   campaign plan), threaded to every practice loop; ui.mode config stays
   the persistent choice. NOT yet screen-aware: the conversational
   surfaces themselves (plan proposal/refinement, capture, inbox) — they
   render transcript-style in both modes. Full unification needs the
   SessionRenderer abstraction extended to conversations. Your in-place
   question: a hybrid is feasible — a bounded live region that redraws
   the CURRENT card in place (cursor-up + erase, no alt-screen) and
   collapses finished cards into normal scrollback, so the terminal
   stays usable and history stays scrollable. Line-based input makes
   Enter tractable (we know the card's height); the REAL risk is
   wrap/resize arithmetic (a mid-card terminal resize breaks
   line-counting and erases the wrong rows) — needs width-aware
   re-measure on every redraw. **Default: design doc before any build.**
6e. **Calibration junk detection depth (your directive 2026-07-17)** —
   shipped now: deterministic screen (slash-tokens, symbol-only input
   refused without recording; everything real scores full; display says
   "noted", never "correct"). NOT covered: fluent-looking mash ("asdf
   jkl") passes the screen and scores full. The next rung is an AI
   reality-check per diagnostic answer (~2KB grade call each) — costs
   tokens on every calibration answer for a rare case reflection already
   sees in the raw rows. **Default: deterministic screen only; escalate
   only on field evidence of mash answers polluting calibration.**
6f. **Readable vault export + name-based links (your directive 2026-07-18).**
   You want export to open in Obsidian as genuinely readable notes — headers,
   prose, markdown links (standard links, Obsidian-compatible) with readable
   names instead of ids. Assessment delivered in-session: GOOD idea, wrong to
   pay for it with the lossless export. Recommendation: keep `dojo export`
   lossless (the escape-hatch/trust contract, I7-tested); add a PROJECTION
   export (`dojo export --vault`): notes named by display names, insights
   with receipts inline, standard markdown links between notes — regenerated,
   never parsed back (the journal.md pattern, ADR 018). This composes with
   ADR 018's deferred phase 2 (id↔filename harmonization): land name-based
   links in the LIVE store's projected files too, and the store itself opens
   in Obsidian as a hand-made-looking vault; --vault export becomes the same
   projection to a snapshot folder. **Default: design doc first; nothing
   built until you gate it.**

6g. **Capture core-need audit (your user story 2026-07-18: URL + why →
   agent grabs the transcript → source → plan-aware, why-scoped quizzing).**
   Validated live: the chain URL→fetch→source-with-provenance→route→seeded
   grounded generation EXISTS and works; why rides as Source.mission.
   Three gaps found, in leverage order:
   (1) SKILL.md said "capture the key content" — not "extract what the WHY
   names; one section of a long video is the right scope". FIXED in-session
   (the extraction step is where whole-video-quizzing is actually avoided).
   (2) The why never reaches generation: compile_generate's payload has
   campaign mission + SOURCE slice; Source.mission (your why) is absent —
   why-scoped quizzing currently depends entirely on extraction quality.
   Proposal: capture-seeded generations inject one line beside the slice
   ("why the learner saved this: ..."), budget-visible (~100B), template
   stating it. (3) file_capture's propose_campaign creates a BARE campaign:
   no plan, no calibration phase, no diagnostic-mode stamp (parity gap with
   every other creation door). Proposal: chain the learn machinery — a
   campaign.plan task seeded with why + captured content, review-before-
   trust as always; amends ADR 013's "captures are material, not goals"
   stance for the case where the why IS a goal.
   → **(2)+(3) SHIPPED 2026-07-18** under your parting authorization
   ("continue... we need to improve that part"): why→generation (9257ea0,
   renders only when a why exists — payloads otherwise byte-identical) and
   the plan chain for capture-born campaigns (99ec3a2: propose_campaign
   emits a seeded campaign.plan task; consent = `campaign create
   --from-task <tsk> --into <campaign>`, initialization-only, established
   plans refuse). Interactive-flow surfacing of the plan chain rides with
   display unification (6d).

6i. **Deliberation trap-benchmark + anchor profiles (your directive
   2026-07-19, designed in-session).** Finding: 55/62 battery runs start
   with `{` at byte zero — the skeleton-final prompt pattern-locks token
   one, and the reasoning-neutral license ("anything before it is
   ignored") is a dead letter in practice. Whether that RESTRICTS models
   that think by outputting (~4B; internal thinkers unaffected, sub-1B
   measurably hurt by invitations) is unknown. Design (immune to the
   internal-vs-visible-thinker confound — we can't observe thinking, so
   we measure it by its FRUIT): ~2 TRAP scenarios per task kind (visible
   corpus) where shallow pattern-completion yields a specific detectable
   wrong answer and the right answer requires composing 2-3 non-adjacent
   constraints (grade: right-result-broken-method; reflect: aggregate vs
   latency×topic decomposition + distractor; plan: deadline forces
   cutting the dependency root; route: lexical-match campaign vs
   semantic owner; generate: insight-collision engineering; diagnostic:
   jointly-implied open axis). Then batteries per (model × anchor):
   (A) current neutral anchor vs (B) bounded-invitation fragment worded
   as the STRONGEST known elicitor, activity words not format words
   (owner probe 2026-07-19: "prose" names a format, not the activity —
   a weak invitation false-negatives the whole experiment): "If two
   outputs seem defensible, think it through step by step first — write
   your thinking, then the JSON. Only the last JSON object counts."
   Compiler-selected by a fulfiller PROFILE,
   never model judgment (craft rule 5). B−A per model = the restriction
   effect; pre_bytes confirms mechanism. Pre-registered rule: adopt the
   invitation as an OPT-IN profile only if trap-avoidance rises
   materially at some caliber, neutral floors regress nowhere, and
   bytes/latency hold (mutual non-regression, both directions). 2
   replicates per cell (±3 kind variance); codex cell = one spot set,
   spend-gated on you (expected flat — that flatness itself proves the
   anchor doesn't restrict internal thinkers). This SUBSUMES the
   "reasoning" JSON-field idea (same hypothesis, riskier encoding: long
   free-text is where ≤4B models break JSON — README failure mode 5).
   **ANSWERED BY MEASUREMENT 2026-07-19 (8-cell grid, 2 replicates/cell,
   12 deliberation-trap scenarios, deterministic trap detectors):**
   caliber-DIVERGENT. qwen3.5:4b takes the invitation (pre_bytes 0→~450)
   and trap-avoidance rises 44%→75% of measurable rows with rejects
   flat; gemma3:4b ignores it entirely (pre_bytes unchanged) and gets
   slightly worse (avoided 15→12, rejects 2→4) while already at ceiling
   under the neutral anchor (0 trap hits in all 4 neutral+invited
   cells... 0 hits total). ADOPTED as the opt-in
   `fulfiller.anchor_profile: deliberate` config (compiler-appended,
   default neutral byte-identical) with guidance: qwen-class visible
   thinkers only. The codex B cell was deliberately skipped (your
   pre-reg expected flat = low information; spend discipline) — say the
   word if you want it run. Judged floors for the 12 trap scenarios
   bootstrap on the arm-A codex run.

6j. **Link-enrichment for tool-capable fulfillers (your question
   2026-07-19).** Capture-time fetching by the harness is shipped
   doctrine (6g). The strong form — payloads carrying only a link,
   fulfiller fetches at generation time — violates three invariants
   (offline floor / model-strength neutrality: local models can't fetch
   and would silently produce ungrounded items; provenance: grounding
   dojo never saw weakens review-before-trust; ADR 009/010 injection
   surface: third-party page content flowing into the store's writer).
   Soft form recommended: SOURCE slice stays the sufficient floor,
   locator rides as information; a tool-capable fulfiller MAY consult
   the full source (§1b surplus-intelligence side-channel; local models
   ignore it at zero cost). Needs benchmark scenarios (noise is the
   test) + fetch-failure-never-blocks rule. **Default: design only;
   nothing built until you gate it.**

6h. **Session abandonment as evidence (found 2026-07-18, README-truthfulness
   check).** `/quit`//`/exit` pause the session and leave NO attempt row —
   reflection cannot see abandonment patterns (your real avoidance insight
   only exists because you typed "exit" as an ANSWER). If quits carried an
   honest, non-punitive event row (never a score), avoidance-when-unsure
   would be detectable without the learner mistyping. Tension to weigh:
   no-guilt rules — quitting must never read as failure. **Default: not
   built; needs a design that records without judging.**

7c. **Blog strategy delivered (your directive 2026-07-18):**
   `docs/growth-blog-plan.md` — six posts in your voice with the standing
   honesty frame (AI wrote the diffs under your method; the decisions,
   rulings, and receipts are yours), mined from the 85 owner-ruling
   commits, the ADR arc, and the archived implementation. P1 method-meta ·
   P2 blind holdout · P3 keys-taken-back arc · P4 no-guilt (Show HN
   anchor) · P5 receipts (your avoidance-insight story) · P6 weak-model
   failure modes. Sequenced against growth §6. **Default: drafts are
   yours to write; I can draft any post's skeleton on your word.**

7b. **HN pulse readiness + repo description (your asks 2026-07-18).**
   "Pedagogy harness" goes in your HN post (your call, recorded). Timing
   recommendation delivered in-session: a SEQUENCE, not a date — v1.0.0
   tagged (drops→holdout gate) → repo public + docs hosted + demo GIF
   (Phase 0) → Phase 1 soft channels breathing for weeks → pulse; ideally
   with Anki A1 so the r/Anki post rides the same week (growth §6: the
   pulse is deliberately last; ~one shot per 12-18 months). Heuristic: when
   someone you didn't recruit files an issue or posts a scorecard, launch.
   Repo DESCRIPTION → **SET 2026-07-18 on your word** (gh repo edit):
   "Your AI can teach you anything. Dojo makes it stick — a deterministic
   pedagogy harness for whatever model you already run." Same phrase now
   spans README capstone · blueprint §2 · repo card · your future HN post.

7. **Growth strategy sign-off** — full researched strategy delivered at your
   direction: `docs/growth-strategy.md`. Headline: retention is already the
   product (the SRS community's documented abandonment causes map 1:1 onto
   shipped design decisions); distribution rides AI-harness marketplaces
   first, the Anki community second (needs interop A1 → interacts with
   decision #2), launch pulse deliberately LAST. Phase-0 prerequisites are
   concrete: holdout gate + v1.0.0 (decision #1), repo public (decision #3),
   docs site, demo GIF, packs. **Default: no public move until you approve
   the doc and its prerequisites.**

8. **Standalone binary + non-dev barrier (your question 2026-07-18).**
   Assessment: YES it's buildable — deps are four small libraries
   (PyYAML/rich/pydantic/fsrs), git already optional, and install.sh's
   Step 3 + PyInstaller hint anticipated exactly this. But the cheapest
   barrier-killer is NOT the binary:
   - **(a) uv fallback in install.sh (recommended first move, ~15 lines,
     zero release infra):** today the script dead-ends only when the
     machine has no Python 3.11+ and no published binary exists. Insert a
     step: no compatible python → `curl -LsSf https://astral.sh/uv/install.sh
     | sh` → `uv tool install git+https://github.com/Stan15/dojo` — uv
     ships its own standalone Pythons and handles ~/.local/bin shims. This
     closes the Python prerequisite on mac/linux entirely.
   - **(b) PyInstaller release matrix (the actual binary):** GitHub Actions
     on tag → `dojo-{os}-{arch}` artifacts that install.sh Step 3 already
     downloads. Real costs: ~40-60MB artifacts, onefile cold-start lag,
     and — the hidden one — **macOS Gatekeeper**: an unsigned binary gets
     quarantined on download, and "right-click → Open" is a WORSE non-dev
     experience than the script path. Shipping (b) honestly means an Apple
     Developer ID + notarization ($99/yr + CI signing) or mac users stay
     on (a). Linux has no such tax; Windows (no sh at all today) is its
     own separate decision.
   - **(c) The real non-dev front door is the AGENT, not the terminal:**
     our persona's non-dev never runs curl — their agent does (the skill
     self-bootstraps since fd1f9f7, and the new bootstrap_fresh_machine
     scenario now measures exactly that flow). Every install-path
     improvement should be judged by "can the agent walk it unattended".
   **Worth it?** (a) now — it's the only current dead-end and costs almost
   nothing; (b) when field evidence shows (a) failing or Windows demand
   appears, and only WITH signing on macOS. **Default: build (a) on your
   word; (b) stays gated (needs the signing spend decision); Windows
   support ledgered but unscheduled.**

_Parked by your explicit rule (not decisions, just recorded): interleave
share tuning and OP #13 exact-undo — both wait for real usage data._

## Decided & shipped — 2026-07-09 ledger (detail preserved)

0. **Daily acquisition discipline** (your field report: second daily run was
   generating AND serving new material). Ruling implemented: reflection
   fires at daily START on settled evidence (grades land async, so
   end-of-session reflection would read pending rows — start-of-next-daily
   is the robust point; it also still fires in the complete_for_today
   state). Once today's practice happened: daily emits NO generation
   (replenishment waits for tomorrow's first run), and a would-be packet of
   purely never-practiced stock is held ("new_stock_held_for_tomorrow") —
   genuinely due reviews still serve (retention ≠ acquisition). `dojo more`
   stays the only post-completion acquisition door, with its own sourcing
   kept deliberately distinct from daily (never serves reviews,
   debt-guarded, once/day, origin-marked) rather than wrapping daily.

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
