# Dojo v1 Blueprint

_Status: authoritative design, 2026-07-07. Supersedes stale portions of README and
`docs/api-specification.md`; consistent with `product-north-star.md`,
`pedagogy-foundation.md`, and ADRs 001–013 (010–013 govern where earlier ADRs
conflict). Approved for implementation when the product owner opens the gate in
`docs/STATE.md`._

---

## 1. The promise, restated as an engineering problem

The user consumes far more educational content than they retain, and has more
skills-to-learn than time to learn them. Dojo's promise: **a daily, bounded,
non-intimidating practice ritual that turns whatever you cared enough to capture
into durable ability — personalized by evidence, grounded in your own trusted
sources, and driven by whatever AI you already use.**

Decomposed, that is five hard requirements:

| Requirement | Engineering consequence |
|---|---|
| Daily & non-intimidating | Bounded packet composition is a **code-enforced invariant**, not a prompt suggestion |
| Actually retains | Deterministic spaced-retrieval engine (facts) + novelty scheduling (skills), evidence-driven |
| Deeply personalized | Campaign-scoped learner state, distilled by reflection, injected compactly into every generation |
| Unknown model quality | All AI output is schema-validated proposal; the core never lets a weak model corrupt state |
| AI harnesses are the users | Install a skill → it just works: no API keys, no daemons, minimal context footprint |

## 2. The one load-bearing split

Everything in this design follows from one separation:

- **The deterministic core (Python)** owns everything that must give guarantees:
  state, storage, scheduling math, session lifecycle, queue caps, provenance,
  validation, telemetry. It is fully functional offline, with zero AI.
- **Intelligence (whatever model shows up)** owns everything that needs judgment:
  drafting exercises, grading free-form answers, reflecting on evidence, planning
  syllabi, routing captures. It participates **only** through single-turn,
  schema-bound **Tasks** (§6).

A weak model can produce a bad exercise (caught at review), a bad grade (correctable
via `dojo correct`), or an invalid payload (rejected at the boundary). It cannot
mis-schedule, overflow a queue, lose provenance, or corrupt the store. That is the
"strong guarantees even with weak models" property, located in one place.

## 3. Concepts — eight, no more

1. **Source** — trusted material with provenance. Any size: a book chapter, an
   article, a transcript, or a one-sentence capture (§8). Unified per ADR 001:
   its heading hierarchy is also its topic outline.
2. **Campaign** — a learning goal in execution: mission, syllabus/topic tree, plan
   phases, strategy profile, insights, evidence. The unit of personalization
   (ADR 004) and of attention allocation (§7).
3. **Topic** — a stable node in a campaign's tree. The attachment point for skill
   mastery state and for grounding references. Stable-node identity is what keeps
   scheduling state from bloating (§7).
4. **Exercise** — one practice item. Lifecycle: `candidate → active → retired`.
   Kind: `recall` (static, repeats verbatim) or `skill` (generative, disposable).
5. **Attempt** — evidence: answer, score, latency, skip reason, feedback.
6. **Insight** — a consolidated, campaign-scoped learner hypothesis
   (misconception, preference, goal), with evidence links and an active/resolved
   status.
7. **Task** — a pending unit of AI judgment: compiled minimal context + output
   contract + lifecycle (`pending → fulfilled | failed`). The only seam between
   core and intelligence.
8. **Packet** — one day's bounded, interleaved practice selection. The product's
   face.

Everything else (sessions, runs, inbox) is bookkeeping on these eight.

## 4. Invariants

Stated once, tested forever. Each maps to at least one test in the milestone plan.

- **I1 — Provenance.** Every active exercise either carries source refs
  (`source_id` + span) or is tagged `origin: synthetic`. No third state.
- **I2 — Review-before-trust.** Nothing enters active practice without passing the
  candidate gate. Policy may auto-accept (configurable per campaign), but the gate
  and its outcome are always recorded.
- **I3 — Non-bombardment.** Packet size ≤ configured cap (default 5, hard max 8);
  active due queue per campaign ≤ 20. Enforced in code; violations impossible, not
  discouraged.
- **I4 — Offline floor.** `dojo daily` always produces a usable session with zero
  AI available: due `recall` items are served; missing generation is reported
  honestly ("2 skill slots skipped: no fulfiller"), never faked.
- **I5 — Validation boundary.** No AI output mutates state except through task
  submission, which validates against the task's schema. Invalid → rejected with
  actionable errors, state unchanged, bounded retries (2), then `failed` + honest
  degradation.
- **I6 — Token budgets.** Every compiled task payload respects per-section and
  total byte budgets, asserted in tests against representative fixtures. SKILL.md
  stays ≤ 60 lines. Truncation is marked, never silent.
- **I7 — Storage contract.** Every entity round-trips losslessly through the store.
  All store implementations pass one shared conformance suite; the markdown format
  is a documented public contract (§5).
- **I8 — Deterministic scheduling.** Packet selection is a pure function of
  recorded state + clock (+ seeded tie-breaks). Same state, same day → same packet.
- **I9 — Explainability.** Every selection/scheduling decision has a one-sentence
  plain-language reason, exposed via `dojo why` and in envelopes.
- **I10 — Honest degradation.** Anything skipped, truncated, unfulfilled, or
  approximated is counted and surfaced. (Scores produced by AI grading are tagged
  `grader: ai`; self-reported ones `grader: self`.)

Proof-effort allocation (method §0): the compounding-flaw zones are the
**scheduler** (I3, I8), the **store round-trip** (I7), and the **task boundary**
(I5). Those get written correctness arguments (§7, §5, §6) and property-style
tests. CLI wiring and rendering get behavioral tests and a clear head.

## 5. Storage — one protocol, markdown canonical, Postgres later

### The protocol

Domain code speaks a `Store` protocol: typed repositories per entity, ID-based
references only (fixes the current path-leak in `Attempt.session`/`.exercise`),
query by declared filters. No file paths, no SQL, no YAML above the protocol.

```
Store
 ├── sources / campaigns / topics / exercises / attempts / insights / tasks
 ├── sessions, inbox, config
 └── audit(message)          # backend-appropriate versioning hook
```

Selection via `store.backend = markdown | postgres` in config. **The conformance
suite is the contract**: one shared pytest suite parameterized over backends; a new
backend ships only when the suite passes. That is the entire cost of "switch to
Postgres for the app later" — no domain changes.

### The markdown backend (canonical, v1)

Human visibility is a product feature: a learner can open `~/.local/share/dojo/`
and read their entire learning life. Layout (evolving the current store, keeping
its good bones — frontmatter + body, mtime index, atomic writes, file lock):

```
~/.local/share/dojo/
  config.yaml
  inbox/cap_<id>.md                    # unrouted captures (§8)
  sources/src_<id>.md                  # frontmatter: provenance; body: content
  campaigns/camp_<id>/
    campaign.md                        # frontmatter: mission/strategy/status; body: syllabus
    plan.yaml                          # phases, criteria
    topics.yaml                        # per-topic mastery + due state (§7) — ONE file
    exercises/…  attempts/…  insights/…
    journal.md                         # pedagogical journal (append-only)
  tasks/tsk_<id>.md                    # pending/failed task envelopes + run traces
  archive/…
```

Format rules (public contract, kept in this doc):
frontmatter = schema fields with defaults omitted; body = the entity's one
designated long-text field; IDs stable and content-independent; filenames are
presentation, IDs are identity (rename-safe). Git versioning batches **one commit
per CLI command**, not per entity write (fixes current per-save noise), and commit
failures surface in `dojo doctor` rather than being swallowed.

**Correctness argument (I7).** Lossless round-trip holds iff (a) every schema field
is representable in YAML frontmatter or is the designated body field, (b) the
omit-defaults serializer and the defaults-aware parser are exact inverses, which is
guaranteed by deriving both from the same Pydantic model definitions, and (c) body
extraction is unambiguous, which holds because exactly one field per entity maps to
the body. Pinned by property tests: generate entities (seeded), write, re-read,
assert equality; plus golden fixtures for human-edited files (unknown fields
preserved via a `extra` passthrough, so a learner editing frontmatter can't be
silently destroyed).

## 6. The Task contract — how intelligence plugs in (ADR 010)

### Why inversion

The prototype shells out to an AI subprocess. But the priority deployment **is an
AI harness driving the CLI** — an intelligent model is already present. Spawning a
second one costs a second bill, requires connector/API-key setup (breaking
"install the skill → just works"), triggers permission prompts (the exact problem
ADR 009 fought), and adds a failure mode. So v1 inverts control:

```
harness runs: dojo daily --json
  ← envelope: { data: …, tasks: [ {id, kind, prompt, output_contract, submit} ] }
harness fulfills each task ITSELF (it is the model), then:
harness runs: dojo task submit tsk_x --file result.json
  ← envelope: { ok, applied: …, errors?: […] }
```

- **Fulfillment adapters:** (1) host harness inline — default, zero config;
  (2) subprocess connector — kept, demoted, for headless/cron use (`dojo task run`
  drains pending tasks through a configured command); (3) future: API provider
  for the app. All three fulfill the *same* task records — one contract, no
  special cases.
- **Single-turn value injection preserved** (ADR 009): the core compiles the full
  context; the fulfiller never explores state, so prompt-injection surface and
  token loops stay closed. Task payloads are also *files* (`tasks/tsk_<id>.md`), so
  a fulfiller can be pointed at a path instead of re-emitting content through the
  conversation — context touches the model exactly once.
- **Sync where it matters:** commands that conversationally need a result *now*
  (grading an answer mid-session) emit the task in the same envelope that reports
  the answer as `pending_grade`; the session continues; the grade lands when
  submitted. Nothing ever blocks on AI.

**Correctness argument (I5).** State mutation from AI occurs in exactly one code
path (`task submit` → Pydantic validation → typed applier per task kind). Each
applier is idempotent (resubmission of the same task id is a no-op after success)
and total (every validated payload maps to a defined state change; anything else
was rejected at validation). Therefore invalid or duplicate AI output cannot
corrupt state; the worst case is a `failed` task, which I4/I10 degrade honestly.
Pinned by: applier unit tests per kind, idempotency tests, and fuzzed invalid
payloads asserting state-hash unchanged.

### Task kinds (closed set, v1)

| Kind | Purpose | Trigger |
|---|---|---|
| `exercise.generate` | Draft N candidates (grounded or synthetic) | retain-lane topic due with no stock; advance-lane frontier entry |
| `attempt.grade` | Score free-form answer against rubric | answer submitted for rubric-bearing exercise |
| `campaign.reflect` | Distill evidence → insights, strategy, plan revisions | periodic (attempt-count/staleness thresholds), or `dojo reflect` |
| `campaign.plan` | Goal → syllabus + phases + refinement questions | `dojo campaign plan/create` |
| `capture.route` | File a capture into campaign/topic (or propose new) | `dojo capture` |

Prompts for all five are designed artifacts: `docs/design/prompts.md`.

## 7. The pedagogy engine — scheduling as allocation + memory (ADR 012)

The user's framing ("spaced repetition across campaigns, then within a campaign")
names two genuinely different problems. Solving each with its proper tool is what
keeps the system small:

### Tier 1 — attention allocation across campaigns

Campaigns don't forget; learners under-attend them. So Tier 1 is **not** SR math —
it's urgency-weighted fair rotation. Each campaign gets a deterministic priority:

```
priority = w_due·due_pressure + w_atrophy·days_since_touch
         + w_deadline·deadline_proximity + w_user·user_weight
```

`dojo daily` ranks campaigns, fills the packet's slots proportionally from the top
(interleaving ≥ 2 campaigns when possible — desirable difficulty), and every choice
carries its one-line reason (I9): *"French: 6 items due, untouched 3 days, exam in
12."* All weights visible in config; no LLM involvement.

### Tier 2 — two lanes inside a campaign

- **Retain lane.** Memory state attaches to the *stable node*:
  - `recall` exercises (facts): FSRS-inspired per-item state — `{due, stability,
    difficulty, reps, lapses}` — few floats in frontmatter, updated by a pure
    function of (state, score, latency, clock).
  - `skill` topics: per-**topic** SR state in `topics.yaml` — `{level, due,
    last_outcome}`. When a skill topic comes due, the scheduler requests a **novel**
    exercise (`exercise.generate`) instead of repeating an old one (ADR 007's
    novelty principle). Old skill exercises retire after use.
    *Anti-bloat argument:* items are disposable, so per-item state for them is
    state for things that never recur; attaching memory to topics bounds scheduling
    state by the size of the syllabus, not the practice history.
- **Advance lane.** The frontier: next unmastered topic of the active phase, gated
  by phase criteria (accuracy/attempts). Advancing is deterministic; *revising the
  plan itself* is judgment and belongs to `campaign.reflect`.

### Packet composition (I3, the daily face)

Per pedagogy-foundation, scaled to the packet's slots per campaign:
one maintenance item (easy, due) + one weak item (recent lapse / active-insight
target) + one frontier item + optionally one new item. Composition is a pure
function; property tests assert caps, lane mix, and determinism (I8) across
generated state fixtures.

**Correctness argument (I3+I8).** The packet builder consumes only store state and
the clock, uses seeded tie-breaking, and clamps every count before emission
(`min(cap, …)` at a single choke point). Bombardment would require either a second
emission path (none exists — `daily`, `start`, and queue promotion all pass the
same gate) or a cap bypass (grep-able, test-pinned). Pinned by property tests over
randomized store states: `len(packet) ≤ cap` always; identical state+date ⇒
identical packet.

## 8. Capture — "I just learned X" (ADR 013)

Fundamental need: **capture at the moment of encounter must cost one utterance and
never block on filing.** Filing questions at capture time kill the habit; unfiled
items kill the system's coverage.

- `dojo capture "<text>" [--why "<mission note>"]` writes a **micro-source** to
  `inbox/` immediately (durable before any AI runs), and emits a `capture.route`
  task carrying a *compact registry digest* (campaign names + missions, one line
  each + topic tree paths — budgeted, I6).
- The route result proposes: `attach(campaign, topic_path)` | `new_topic(campaign,
  parent, name)` | `propose_campaign(name, mission)` | `stay_inbox(reason)`, with
  confidence. The core **validates the target exists** (weak-model safety), then:
  high confidence → auto-file (Q6 default) with the route recorded in provenance,
  reversible via `dojo inbox`; low confidence or `propose_campaign` → stays in
  inbox, surfaced in the next `daily` envelope ("1 capture awaiting a home").
- A routed capture is a Source like any other: it grounds a fact-candidate
  immediately (capture → candidate in one flow), subject to the same review gate
  and queue caps as everything else. No new pipeline — captures are just the
  smallest sources.

## 9. Context & token economy — engineered, not hoped for

The system will be driven by models of unknown quality on someone else's token
bill. Three mechanisms, all tested (I6):

1. **Budgeted context compilation.** Every task payload is assembled from ranked
   sections — (1) task instruction + output contract, (2) strategy/mission digest,
   (3) active insights (top-K, one line each), (4) grounding slice
   (heading-window resolution, kept from prototype), (5) recent-attempt window
   (compact rows: topic, score, error-tag — never full bodies). Each section has a
   byte budget; lower-ranked sections truncate first; truncation is marked. Total
   default cap ~8 KB/task. Budgets live in config; tests pin them on fixtures.
2. **Generation-side discipline.** Output contracts are compact **example
   skeletons with inline constraints** (weak models follow examples; formal JSON
   Schema stays server-side in Pydantic for validation — the schema is for the
   machine, the skeleton is for the model). Counts are exact ("exactly 3"), text
   fields carry word caps enforced by validators, and the prototype's unbounded
   mandatory `thinking` field becomes a bounded `plan` field (≤ 2 sentences) only
   where planning measurably helps.
3. **Interaction-surface discipline.** SKILL.md ≤ 60 lines (trigger + envelope
   protocol + nothing else); every JSON envelope carries a short `next` hint so the
   agent never needs documentation in context; `--help` is the manual, loaded only
   on demand. Every task run records `payload_bytes`/`response_bytes`;
   `dojo stats` shows where tokens go (observability, §11).

## 10. Milestones — tests named before code, delegation planned

Gate for every commit: `python -m pytest -q` green. Each milestone lists the tests
that prove it; fixtures precede implementations for anything format-shaped.

- **M0 — Truth pass** *(delegate: cheap model, tight spec; lead reviews)*
  Fix pyproject deps (add pydantic, drop fpdf2), renumber duplicate ADR 003,
  align versions, purge build artifacts + gitignore, rewrite stale
  `api-specification.md`/README sections to match this blueprint.
  *Proof: suite stays green; `git grep -l sqlite3 docs/` empty.*
- **M1 — Domain + Store protocol + markdown backend** *(lead)*
  ID-based entities, `Store` protocol, markdown conformance + round-trip property
  suite (I7), one-commit-per-command audit batching, `doctor` extended to format
  validation. Collapse the pass-through facade. Delete `archived_implementation/`
  at close (Q4). *Proof: conformance suite; seeded round-trip; human-edit
  passthrough fixture.*
- **M2 — Task contract + prompts** *(lead; prompt fixtures first)*
  Task entity + lifecycle, envelope emission, `task submit/run`, appliers per kind
  (idempotent, fuzz-tested — I5), budgeted context compiler (I6 tests), prompt
  templates from `design/prompts.md`, connector adapter re-seated on task records.
  *Proof: applier idempotency; invalid-payload state-hash tests; byte-budget
  assertions.*
- **M3 — Pedagogy engine** *(lead)*
  FSRS-lite (pure, seeded property tests), topic-level skill SR, Tier-1 allocator,
  packet builder (I3/I8 property tests), `dojo daily`, `dojo why`, offline floor
  (I4 test: no fulfiller configured → session still works, skips counted).
- **M4 — Capture + reflection + planning** *(lead)*
  `dojo capture`, inbox, `capture.route` applier with registry validation;
  `campaign.reflect` with sliding window (ADR 008) writing insights/journal within
  code-enforced rails; `campaign.plan`. *Proof: route-to-nonexistent-target
  rejection tests; reflection cap tests (insight count bounds).*
- **M5 — Agent experience** *(mixed: skill+installer spec-able to mid-tier)*
  Rewritten ≤ 60-line SKILL.md, envelope `next` hints, installer refresh,
  `dojo stats` token telemetry. *Proof: SKILL line-count test; envelope-protocol
  golden tests.*
- **M6 — End-to-end + ship v1.0** *(lead; verification per method §11)*
  Drive the real loop from a real harness session (capture → route → daily →
  answer → grade → reflect), LOOK at the artifacts, fix what only reality reveals,
  finalize docs, tag v1.0.
- **Backlog (explicitly not v1):** Postgres backend (conformance suite makes it a
  bounded task), the app, PDF packets, semantic retrieval for huge sources,
  multi-learner.

## 11. Observability & degradation surfaces

`dojo why` (every scheduling choice, one sentence), `dojo stats` (retention,
atrophy, token spend per task kind), `dojo doctor` (store validation, git health,
task-queue health), task run traces in-store (payload/response byte counts,
validation error history), and honest counters in every envelope (`skipped`,
`truncated`, `pending_tasks`, `unrouted_captures`). The learner's git log doubles
as a complete audit trail of their learning life.

## 12. What this design deliberately rejects

- **A second LLM bill via mandatory connectors** — the harness is the model (§6).
- **LLM-side scheduling** — date math by vibes is how retention silently dies (§7).
- **Per-item state for generative skills** — bloat with no memory being modeled (§7).
- **Global learner profile** — cross-campaign contamination and unbounded prompts
  (ADR 004 upheld).
- **Big upfront generation** — ADR 003b upheld; JIT with stock-ahead-of-need only.
- **Capture-time filing questions** — the habit dies (§8).
- **Prompt-enforced invariants** — anything that must be true is enforced in code;
  prompts only improve quality above the floor (§2).
