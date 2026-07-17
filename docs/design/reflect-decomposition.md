# Reflect decomposition — investigation & proposal (STATE 7d)

_Status: PROPOSAL awaiting owner gate (directed 2026-07-11, "investigation
before design — deliverable is a proposal, not implementation"). Nothing here
is authoritative until the owner opens the gate. Authored by a fresh session
per the 7e contamination ruling._

## 1. The problem, measured

`campaign.reflect` is one model call carrying **five jobs** (six outputs):
insight adjudication, strategy calibration, plan revision, clarifying
questions, topic retirement, plus the journal. Evidence that this is an
anti-pattern rather than a style preference:

- **Multi-sample variance is the symptom the owner named.** Three post-ADR-017
  samples of `legitimate_restructure` spanned 0.67–0.89 *with a different
  criterion dropped each run* (baseline floor_note, owner-approved). The model
  isn't failing a skill; it's rationing attention across six concerns and
  dropping a different one each time.
- **The instruction body is the fattest in the system and at its ceiling.**
  Reflect's compiled instruction block is ~3.7 KB of the 6144 B total budget;
  five reflect scenarios (visible + holdout) sit within 4–68 bytes of the cap
  (measured 2026-07-11 during the floor-work session — a one-line rule edit
  broke five previously-green scenarios). Every new concern ADR 017 added
  (retirement, TRENDS, question fulfillability) grew the rule set, and the
  rules now interact: no-change bias vs resolution-is-a-finding vs
  retirement-needs-voice vs the rushing carve-out. There is no headroom for
  the next pedagogy surface.
- **Weakest category in the corpus.** The weak-floor ledger is dominated by
  reflect scenarios (extension-binge 0.00, diagnostic-voice-revision 0.33,
  learner-contradicts 0.33, learner-language 0.10 pre-fix). The other task
  kinds — each a single job — mostly sit at 0.8–1.0.
- **Model-strength neutrality (the product bet) points the same way.** A 4B
  local model can adjudicate one insight against fifteen attempt rows; it
  cannot hold six interacting rule clusters. Single-job calls are exactly the
  floor-not-ceiling shape (prompts.md §1b): a weak model executes each simple
  contract; a strong model just does them all well.

Root cause, stated once: **reflect violates our own craft rule 5** ("branching
happens in the compiler, not the model"). The template asks the model to
decide, per run, *which of five jobs today's evidence warrants* — that
decision is judgment-shaped but largely computable, and we already know what
models do with computable branching: they drop branches.

## 2. Candidate shapes weighed

### A. Fixed three-pass split (adjudicate → calibrate → govern)
Always three sequential calls; each output feeds the next.
- Cost: payload union ≈ 8.5 KB + three responses vs today's ~6 KB + one —
  roughly **+50% tokens every reflection**, on the daily heartbeat path.
  Latency triples (sequential; calibrate wants adjudication's verdicts).
- Verdict: **rejected.** Pays the decomposition tax on every run, including
  the (deliberately most common) nothing-happened run. Token spend is the
  owner's money.

### B. Model-led triage → act
A cheap first call classifies which jobs the evidence warrants; warranted
sub-tasks are then emitted.
- Verdict: **rejected.** Re-creates the exact failure at a different altitude:
  the triage call is itself a "which branches apply" judgment by a model, and
  a dropped branch is now *invisible* (nothing downstream ever runs). Also
  adds a call on every run.

### C. Compiler-decided conditional sub-tasks  ← proposed
Two task kinds; the **deterministic core** decides what to emit (craft rule 5
honored — the model only ever executes a mode):

- **`reflect.adjudicate`** — always emitted (it is the reflection heartbeat).
  Payload: INSIGHTS + ATTEMPTS (+ FEEDBACK). Output: per-insight verdicts
  (update/resolve/create), journal line. This is the only job that needs
  *every* run: insights are the learner model, and an unexamined insight is a
  silent error. ~3.5 KB payload — **cheaper than today on the typical day**.
- **`reflect.govern`** — emitted ONLY when deterministic triggers fire, with
  only the sections its triggers need:
  - window accuracy crosses a threshold band (>0.85 / <0.50, computable) →
    strategy section; the dead-zone middle emits nothing and strategy is
    null *by construction*, not by model restraint;
  - learner FEEDBACK present, stuck-detector (2 sessions, no criteria
    progress), or a MISSION deadline → plan-revision + questions sections;
  - TRENDS over-mastery flags or a resolved insight naming a topic →
    retirement section.
  Authority rails (`authority.py`) consume its output unchanged — the
  contract is the same PlanRevision/StrategyChange/TopicRetirement shapes.

Cross-job couplings move to where they belong:
- The **rushing carve-out** (fast-miss/slow-success ⇒ insight + scaffolding,
  not difficulty) is *detectable deterministically* (score×latency over the
  window). The compiler stamps the govern payload with the computed signal
  ("misses fast, successes slow") instead of asking the model to derive it —
  the model interprets, never detects.
- `reflect.adjudicate` runs first; a resolved insight or a created one rides
  into the govern payload as one line (same mechanism as today's
  learner-voice evidence).

**Cycle semantics** (the new complexity, priced): a reflection cycle = the
adjudicate task + zero or more govern tasks emitted together. Attempts are
marked `reflected` when the *adjudicate* task applies (it is the job that
consumes them as evidence); govern tasks carry the cycle id and re-surface
via the existing stale-task machinery if unfulfilled. No new storage: journal
entries already carry task ids.

### Cost model (typical week, one campaign)
Today: 7 reflections × ~6 KB+response ≈ 7 × 1.6k ≈ **11k tokens**.
Proposed: 7 × adjudicate (~1.0k) + ~2 × govern (~1.1k) ≈ **9.2k tokens** —
the quiet majority of days gets cheaper; eventful days pay one extra small
call. Latency: unchanged on quiet days; +1 sequential call on eventful days —
acceptable because reflection rides the daily heartbeat, not an interactive
answer path.

## 3. What it buys beyond variance

- **Sharper evals per job**: a judge criterion maps to one task's contract;
  the multi-criterion attention-rationing variance disappears mechanically.
- **Budget headroom**: each template carries only its own rules; the next
  pedagogy surface (there will be one) lands in the task it belongs to.
- **Weak-model program**: the qwen3:4b / gemma3:1b bake-off gets contracts a
  small model can plausibly pass — the neutrality bet becomes testable.

## 4. Costs & risks, honestly

- Two templates, two appliers, cycle semantics: real engineering (~1 session)
  plus corpus migration (~20 reflect scenarios re-targeted to the right
  sub-task; the shape suite mechanizes most of the checking).
- **Holdout invalidation**: ~9 holdout scenarios compile `fn: reflect`; after
  migration they cannot run. They must be burnt to visible and re-authored
  blind against the new contracts (subagent pipeline, one enrichment pass) —
  a v1.0.0-gate-sized spend to re-bootstrap floors at the next gate.
- The journal fragments across tasks; daily's announce concatenates cycle
  entries (cosmetic, but a real UX diff to review).
- Migration timing: this invalidates baselines and holdout *right after* we
  stabilized both for v1.0.0. **Recommendation: gate v1.0.0 on the current
  mega-task first; land decomposition as the first post-1.0 unit.**

## 5. Proposal for the gate

1. Ship shape **C** (adjudicate always; compiler-triggered govern) as
   post-v1.0.0 work, one milestone: schemas + compiler triggers + two
   templates + appliers/cycle semantics + corpus migration, delete
   `campaign.reflect` in the same commit the replacement lands
   (delete-over-retain).
2. Before building: a **one-scenario spike** — hand-compile adjudicate/govern
   payloads for two existing scenarios (one quiet, one eventful) and run them
   against codex + one weak model, judged by the existing rubrics split by
   job. If the split doesn't beat the mega-task's scores on the same
   scenarios, stop and re-investigate (evidence-gated, like ADR 017's
   enrichment-task rejection).
3. Holdout re-enrichment scheduled with the migration (blind protocol
   unchanged), floors re-bootstrap at the next release gate.

Default if unanswered: nothing is built; the mega-task stays; this document
remains the ledger entry for the decision.
