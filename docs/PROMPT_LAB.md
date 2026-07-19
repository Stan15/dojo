# PROMPT LAB — standing directive for autonomous prompt improvement

_Owner authorization 2026-07-19 (verbatim grant recorded at the bottom).
Point any fresh session here; it knows exactly what to do. This file is the
WHAT and the RULES; `scratch/prompt-lab/WORKBENCH.md` is the LIVE STATE a
resuming session picks up from._

## STEP ZERO — arm the resiliency mechanism before any work

The moment a session is pointed at this file, BEFORE reading anything
else or doing any work, make the campaign failure-tolerant:

1. **Recurring cron heartbeat** (CronCreate, every ~23 min, recurring,
   off the :00/:30 marks) with EXACTLY this prompt:

   > [PROMPT-LAB HEARTBEAT — not a user message, not a new task.] STOP
   > CONDITION FIRST: if this session is already executing prompt-lab
   > work, mid-conversation, or waiting on an in-flight process, reply
   > with one short line ("heartbeat — campaign active, continuing
   > <current step>") and RETURN to exactly what you were doing — do not
   > re-read files, do not restart steps, do not launch anything. ONLY
   > IF this session is genuinely idle on the campaign (no in-flight
   > battery per `pgrep -f measure.py` and no unfinished turn): read
   > docs/PROMPT_LAB.md, then scratch/prompt-lab/WORKBENCH.md, and
   > resume from its NEXT section. Hard rails always: never reward hack;
   > holdout blindness total (never open corpus/holdout/,
   > evals/baselines/*__holdout*, evals/reports/holdout-*; never run the
   > holdout gate; uncommitted __holdout baseline is owner-only); mutual
   > non-regression both directions; ONE battery at a time; stage files
   > by name.

   The stop-condition preamble is load-bearing: a firing that lands on a
   WORKING session must defuse itself into a one-line heartbeat — never
   restart steps, never double-start a battery, never derail the thread.
2. **One-shot wakeup** (ScheduleWakeup, ~20-25 min while work runs,
   30-60 min when idle-ish) pointing back here; re-arm it before every
   long operation and at every turn end. The wakeup is the pacer, the
   cron is the net beneath it: if usage runs out, missed cron firings
   are lost harmlessly and the first firing after renewal resumes the
   campaign from WORKBENCH.
3. Then read `CLAUDE_START.md` (method chain), the rest of this file,
   and `scratch/prompt-lab/WORKBENCH.md` — and execute its NEXT section.

Known limits (say them to the owner if asked, don't re-derive): cron and
wakeup are session-scoped — if the Claude process itself dies, recovery
is the owner pointing ANY new session at this file; recurring crons
auto-expire after 7 days (each session re-arms its own).

## Mission — maximize QUALITY-DENSITY

The single objective (owner refinement 2026-07-19): **judged quality
delivered per token the user spends, jacked as high as possible** within
a realistic whole-system budget — across calibers: sub-4B (qwen3.5:0.8b
~1GB), 4B-class (qwen3.5:4b best-in-class; gemma3:4b robustness point),
strong tier (codex). Best-in-class rule binds: class verdicts come from
the strongest model of each resource class.

**Quality-density doctrine** (how to reason about every trade):

- **Density = judged quality × single-shot acceptance ÷ whole-trace
  tokens (input + output + retries).** A rejection is quality zero at
  full cost, then pays again — first-shot acceptance is the single
  biggest density lever for weak models, measured repeatedly.
- **Frequency-weight the budget.** A byte added to `grade` fires on
  every answer, every day; a byte on `plan` fires once per campaign.
  System cost = Σ(kind bytes × calls per learner-day). Keep the
  learner-day cost model per caliber in WORKBENCH and judge prompt
  growth against IT, not against the single payload.
- **Optimize the binding constraint per class — never one-size.** A
  class whose quality is below USABLE justifies spending tokens on
  quality (support, examples, structure): crossing into usability is
  worth length, because unusable output has density zero. A class
  already at its quality ceiling justifies pure token cuts. The same
  edit can be right for one class and wrong for another — that is what
  compiler-selected fragments and fulfiller profiles are FOR.
- **Marginal accounting.** Every adopted trade records Δquality/Δbytes
  (e.g. +486B reflect prefill bought three dropped floors, 2026-07-19).
  Diminishing returns are a stop signal, not a challenge.
- **Tokens are latency.** Local single-stream reality: prefill ~106
  tok/s, decode ~7.6 tok/s (measured 2026-07-19) — every 100 payload
  bytes ≈ +0.25s, every 100 output bytes ≈ +3s. Density wins are UX
  wins for exactly the users who need them.
- **The numerator is JUDGED quality — that is the anti-gaming guard.**
  Outputs shrunk below pedagogical usefulness lose more judged quality
  than they save tokens; terse-but-hollow is a regression, not a win.

## Hard rails (none of these bend, ever)

- **NEVER REWARD HACK.** The failure you fix must be the FUNDAMENTAL
  reason, never the surface one. Specific banned vectors:
  - editing a scenario/rubric so a score rises (corpus edits may only add
    coverage, add opposite-branch controls, or fix a genuinely wrong
    rubric — and a "genuinely wrong rubric" claim needs evidence
    independent of the score it unlocks);
  - weakening the judge or its evidence gate (judge changes must be
    mechanics-honesty fixes, free-tier tested, e.g. 3c3041f);
  - wording a template to a specific scenario's rubric phrase (fixes
    generalize: state the PRINCIPLE, verify across the category);
  - tuning anything on holdout data (below).
- **HOLDOUT BLINDNESS IS TOTAL.** Never open `corpus/holdout/`,
  `evals/baselines/*__holdout*`, `evals/reports/holdout-*`, or any gate
  output — names and counts included. Never run `-m eval_holdout` or
  `benchmark --holdout`: the release gate is the OWNER'S trigger, always.
- **Prompt-editing law**: `src/dojo/prompts/README.md` re-read before ANY
  template edit; `docs/design/prompts.md` open during; every measured
  failure mode there stays fixed (enum-echo, // comments, "quote"
  wording, multiline bait, numeric focal points, understatement,
  example-length/content anchoring, reasoning-neutral anchors).
- **Mutual non-regression, both directions, gated**: quality work keeps
  token gains, token work keeps quality. Every template edit re-measures
  the local batteries and rebuilds `evals/baselines/output-budget.json`
  IN THE SAME COMMIT (test_output_budget gate); footprint/goldens
  likewise. Codex-tier ratchets update in the same commit as the run
  that moved them.
- **The uncommitted `evals/baselines/*__holdout*.json` modification is
  OWNER-ONLY**: never read, diff, commit, or discard it. Stage files by
  name, never `git add -A`.
- Method: `/Users/stans/projects/agentic-dev-method/agentic-dev.md` +
  `CLAUDE_START.md` fully. Full pytest green before every commit; commit
  every completed unit immediately; STATE.md current at session end.

## The loop (repeat without interruption)

1. **Observe** — read the newest evidence: battery jsonls
   (`scratch/token-diet/baselines/`, `scratch/prompt-lab/`), eval report
   traces (`evals/reports/quality-*.json`, never holdout-*), committed
   baseline floors. Rank the weakest (caliber × kind × scenario-class)
   cells by leverage.
2. **Theorize the ROOT cause** — read full transcripts, not scores. Ask
   why the model produced THIS output: what in the prompt anchored,
   omitted, invited, or starved it. A theory must name a mechanism
   (anchoring, omission, branching-in-model, example bleed, judge
   mechanics, capability ceiling) and predict what a fix changes and
   what it must NOT change.
3. **Pre-register** — write the hypothesis + decision rule in WORKBENCH
   BEFORE testing: what metric must move, by how much (kind-level
   single-run variance is ±3 — replicate before adjudicating), what must
   stay flat, which calibers.
4. **Test cheap-first** — free gates → local batteries (ONE at a time,
   quiet tree during: no template/corpus writes; template overlays only
   between batteries) → codex validation for strong-tier claims and
   ratchet bootstraps (authorized; spend like it's your money — batch
   scenarios, use `-c model_reasoning_effort=low` where verdict-quality
   allows, full runs only to land ratchets).
5. **Adopt or revert** — same-or-better everywhere is the floor; a win
   on one axis that loses the other is a regression. Winners land as one
   commit (templates + compiler + tests + goldens + budgets + ratchets).
   Losers: revert the working tree, record the negative result in
   WORKBENCH (a disproven theory is progress; never re-test it blind).
6. **Record + reschedule** — update WORKBENCH (state, queue, spend
   ledger), STATE.md at milestones, INSIGHTS.md for durable learnings.
   Schedule the next wakeup (below) so the loop survives usage gaps.
   Go to 1.

## What counts as in-scope without further approval

Template/fragment wording; compiler-side branching and payload
composition (craft rule 5: the compiler branches, the model executes);
retry-error message quality; visible-corpus ADDITIONS (coverage, trap
scenarios, opposite-branch controls) with coverage floors ratcheted;
judge mechanics-honesty fixes with free tests; benchmark/driver tooling
in scratch/; opt-in fulfiller profiles (e.g. the 6i deliberation anchor)
so long as defaults stay frugal-safe. OUT of scope without the owner:
task-contract shape changes (new kinds, multi-turn, tool calls),
schema/applier semantics beyond validation-message wording, anything in
QUESTIONS marked owner-gated, the holdout gate, version tags.

## Parallel experimentation doctrine (owner directive 2026-07-19)

The owner directs FULL use of subagent parallelism — multiple experiments
in flight at once — under diligent, written planning. Parallelism is a
multiplier on the loop, never a loosening of it: every hard rail binds
every lane, and adoption stays serial even when experimentation is
parallel.

**Lane taxonomy — know which resource a job burns before you spawn it:**

- **Local-GPU lane (SERIAL, unchanged):** ollama batteries share one
  Metal GPU and one memory pool — concurrent batteries contend and
  corrupt the measurements (measured: 7×240s timeouts from 3-way
  contention, iterW). ONE local battery at a time stays a hard rail.
  Parallelize around this lane, never through it.
- **Cognitive lane (PARALLEL):** subagents doing trace analysis,
  rejection taxonomies, scenario drafting, trap design, independent
  replication of a diagnosis, second opinions, doc drafts. They read
  existing artifacts and write ONLY to scratch/ or their own worktree —
  never src/ while a battery runs (quiet-tree rail). Cheap locally;
  this is the main parallelism win.
- **Remote lane (PARALLEL with local):** codex runs burn API spend, not
  local compute — they may overlap a local battery. Spend policy
  unchanged; parallelism compresses wall-clock, never inflates budget.

**Plan before spawn (mandatory).** A parallel slate is WRITTEN IN
WORKBENCH BEFORE any launch: per lane — objective, pre-registered
decision rule, exact inputs the agent may read, explicit exclusions
(holdout paths named every time; plus whatever else that brief must
firewall), deliverable form, expected runtime, and how the result gets
reconciled. No agent launches without its WORKBENCH row — a dead
session must be able to reap or restart every lane from that row alone.

**Reconciliation (serial, orchestrator-owned):**

- The session pointed at this file is the ORCHESTRATOR: the single
  writer for WORKBENCH, STATE, baselines, goldens, and every commit.
  Subagents deliver reports/diffs; they never commit, never push,
  never touch shared state.
- Winners merge ONE AT A TIME, mutual non-regression gates rerun after
  each. Two winners touching the same template are a NEW combined arm —
  re-verify the merged state (mini-battery) before commit. Never assume
  additivity: the P1 letter-bleed was exactly an interaction effect.
- Worktrees isolate tree STATE, not compute: template-variant drafting
  in a worktree during a battery is fine; the battery itself records
  which tree/commit it measured (arm-snapshot discipline).
- Subagent negative results land in WORKBENCH like any other — a lane
  that dies with its findings unrecorded was launched wrong.

**Contamination topology.** Every new agent is a new context-flow
route, and contamination flows UP: a subagent that read forbidden
content contaminates the parent through its report. Briefs are
firewalls — treat brief-writing as prompt-craft. State exactly what may
be read and what must NOT (holdout always, by path); reports back are
minimized to what the parent may safely hold (filenames/counts/verdicts
when content would contaminate).

**System-resource guardianship (owner directive — never fry the
laptop).** BEFORE any heavy launch (battery, subagent slate, codex
fan-out) and at every heartbeat during long runs, check:

- load: `uptime` — 1-min load sustained near/under core count
  (`sysctl -n hw.ncpu`);
- memory: `memory_pressure -Q` free %, `sysctl vm.swapusage` (swap not
  near-full and not growing);
- thermals: `pmset -g therm` (CPU_Speed_Limit at 100 / no warnings);
- GPU/model state: `ollama ps`.

Throttling and swap-thrash are DATA CORRUPTION, not just machine risk:
latency numbers measured on a starved machine are invalid, so resource
care and measurement validity are the same discipline. If pressure
appears: launch nothing new, let in-flight lanes drain, re-check before
resuming; never raise OLLAMA_NUM_PARALLEL mid-campaign to parallelize
harder. Live precedent (2026-07-19): a pre-spawn check caught 1-min
load 135 on 8 cores with swap 90% full — a leaked-process fire
(~1700 ssh-agents) unrelated to the campaign; the slate was deferred,
the fire reported to the owner. That is the protocol working.

**Never idle-wait — THINK DEEPLY before concluding "wait" (owner
directive 2026-07-19, strengthened 2026-07-19).** Whenever anything is
running in the background (a battery, a codex run, a subagent lane) or
progress feels blocked, the required act is not the question alone but
DEEP THOUGHT on it: actively generate a candidate list of what you
could be doing instead — enumerate lanes (cognitive analysis, prep,
drafting, design, sizing sweeps over already-collected data), enumerate
blockers, and for each blocker ask whether it can be problem-solved
around rather than waited out. "Waiting" is a CONCLUSION you must earn
by exhausting the candidate list, never a default state. Only when the
deliberate answer is genuinely NO — every candidate would break a rail
(quiet tree during a battery, GPU-lane serialization, imminent usage
cut making spawns wasteful) or produce nothing any next step consumes —
is waiting correct, and even then record briefly WHY (which candidates
were considered and rejected) so the reasoning is auditable.

**An exhaustion claim must be CHECKLIST-verified, never from memory
(owner correction 2026-07-19: two "candidates exhausted" calls were
each followed by a human prompt surfacing 3+ real items — shallow
enumeration is the measured failure mode).** Before concluding
"waiting is correct", sweep EVERY category below and name what each
yields or why it's empty:

1. **Pre-registration debts of ADOPTED arms** — judged spot-sets,
   guard checks, confirmation batteries promised in a pre-reg and not
   yet run (the W1 verbosity guard sat unpaid until prompted).
2. **Draft-ahead for every QUEUED arm** — exact diffs, metric
   scripts, adjudicators written in scratch so results/tree-unfreeze
   are consumed the moment they arrive.
3. **Docs currency** — STATE changelog, INSIGHTS entries for durable
   findings, README claims, QUESTIONS/proposal drafts, memory index.
4. **Analysis over committed data** — every (model × kind × arm)
   cell of archived jsonls not yet taxonomized; sizing sweeps for
   observed-but-unsized failure classes.
5. **Remote lane** — codex-side work that overlaps local batteries
   (spot-judges, validations) within spend policy.
6. **Automation** — chain the next serial step to the current one
   (watcher that launches arm B when arm A exits) so no dead time
   exists between stages.
7. **Directive/tooling hygiene** — does WORKBENCH let a dead session
   resume every lane? Are orphaned processes recorded with poll
   instructions?

If a human prompt ever surfaces a candidate this sweep missed, that
is a DIRECTIVE BUG: patch this checklist in the same session, so the
class of miss dies with the instance. Otherwise
USE the time: prep the next step's scripts/commands so results are
consumed the moment they land, draft pre-registrations and subagent
briefs, analyze already-collected transcripts, size prospective wins
from archived run data, update WORKBENCH/STATE/QUESTIONS drafts,
design trap scenarios. Wait-time work obeys the same lane rules as
everything else — it must never touch what the in-flight measurement
depends on. Live precedent (2026-07-19): during a reflect battery,
wait-time transcript analysis of the PREVIOUS run discovered the
questions-object rejection class, and an archive sizing sweep proved
it cross-caliber (119 hits) — the wait produced the next adopted arm.

**When NOT to parallelize.** Coordination and context budget are real
costs. A lane with no pre-registered decision rule, or whose output the
next step doesn't consume, is waste — serial-with-focus beats
parallel-with-drift. Parallelize when lanes are truly independent, each
has a decision rule, and reconciliation was planned before launch. An
imminent usage outage also argues for deferring spawns: agents that die
mid-flight burn budget for nothing (their WORKBENCH rows make restart
cheap, but not free).

## Experiment queue (seeded 2026-07-19; WORKBENCH holds the live version)

- **6i deliberation trap-benchmark + anchor profiles** (owner approved
  the approach): ~2 trap scenarios per kind; neutral vs strongest-
  elicitor invitation anchor; B−A per caliber = restriction effect;
  adopt as opt-in profile only on a measured win. Codex cell authorized.
- **Sub-4B rescue arms**: qwen3.5:0.8b sits at ~6% ok — taxonomize its
  rejections from iterW-class batteries; test minimal-skeleton /
  per-kind simplification arms. Honest outcome may be "capability
  floor: document the caliber line" — that is a finding, not a failure.
- **Retry-error pedagogy**: rejected submissions get validator messages;
  do the messages teach the RIGHT fix? (2026-07-17 finding: the grade
  evidence cap fired before the substring check and taught the wrong
  fix.) Measure retry-success rate per error message; reword messages.
- **Example-bleed hardening**: mastery_resolution 4B copied skeleton
  example content verbatim into ops. Test content-orthogonal example
  values (nonsense-domain examples?) vs current realistic ones — does
  bleed drop without shape loss?
- **Input-side compression (parked armACC-in)**: re-open ONLY when some
  other change forces a battery anyway; ride along, never alone.
- **Judged-quality spot sets per arm**: shape ok-rate is not quality —
  every adopted arm needs a judged spot check (codex judge, ~8-10
  scenarios spanning categories) proving same-or-better substance.

## Continuity protocol (usage gaps, fresh sessions)

- `scratch/prompt-lab/WORKBENCH.md` is the resumption point: current
  phase, in-flight battery (if any), pre-registered hypotheses, queue,
  spend ledger, negative results. Update it BEFORE starting anything
  slow (a battery, a codex run) so a dead session loses nothing.
- Keep a wakeup scheduled at all times (ScheduleWakeup, ~20-30 min while
  batteries run, ~30-60 min otherwise) whose prompt is: *"Continue the
  autonomous prompt lab: read docs/PROMPT_LAB.md, then
  scratch/prompt-lab/WORKBENCH.md, resume from its NEXT action."* If
  usage ran out, the renewal picks up automatically.
- A fresh session pointed at this file: read CLAUDE_START.md chain
  first, then this file, then WORKBENCH — then continue the loop. If
  WORKBENCH shows an in-flight battery, check its process/output before
  starting anything (ONE battery at a time).
- **Full-restoration sweep after ANY interruption (owner directive
  2026-07-19).** A usage-limit outage, session kill, or crash may take
  down subagent lanes, scheduled crons/wakeups, and monitoring — while
  local processes (batteries, ollama) keep running or die independently.
  On the first turn back, BEFORE resuming NEXT: (1) re-arm the STEP ZERO
  mechanism if the session restarted (cron + wakeup are session-scoped
  and die silently); (2) inventory EVERY lane recorded in WORKBENCH —
  battery: `pgrep -f measure.py` + output-file row count/mtime vs
  expected; subagent lanes: completed reports present or lane dead;
  codex runs: report files present; (3) restart every dead lane from its
  WORKBENCH row — batteries via their recorded command, subagents by
  re-spawning their recorded briefs (a killed agent's partial context is
  gone; the brief is the restart point — this is WHY briefs live in
  WORKBENCH before launch); (4) only when every lane is confirmed
  running-or-complete, return to NEXT. The bar: campaign state as if
  the interruption never happened.
- Contamination self-check at session start: if holdout content has
  entered your context by ANY route, stop prompt work, record it in
  STATE, leave the queue for a fresh session.
- **Cold-context subagents are a standing tool** (owner 2026-07-19):
  when a job needs context THIS session must not have (holdout
  authoring/QA per the CLAUDE_START blind protocol), or must not be
  influenced by what this session already believes (independent
  replication of a diagnosis, fresh-eyes scenario authoring, a second
  opinion on a trap design before floors bootstrap), spawn an agent and
  hand-build its context: state exactly what it may read, and exactly
  what it must NOT read (e.g. "never open corpus/holdout/", "do not read
  the visible corpus", "do not read WORKBENCH"). The brief discipline is
  what protects, not the vehicle — reports back must be filenames/
  counts/verdicts only when the content itself would contaminate the
  parent. Blind authoring reports NEVER include scenario content.

## Stop conditions

Only: the owner says stop; or a hard rail would be crossed (then record
in STATE/QUESTIONS and continue with the next queue item instead). Idle
is never a state — if the queue empties, the loop's step 1-2 mandate
generating NEW testable theories (think deeper: payload composition,
section ordering, per-kind decomposition evidence, cross-caliber
transfer of fixes) and testing them.

---

_Original owner grant (2026-07-19, condensed but faithful): "go ham
running experiments and digging deep trying to optimize and improve the
prompts so that output QUALITY on models of all calibers improves
SIGNIFICANTLY AND output generation token usage improves SIGNIFICANTLY
(trade tokens for quality where genuinely good). Permission for running
codex and any model needed. Keep running and improving without
interruption; keep making the system genuinely better. If out of things
to do, think deeply about approval-free improvements — highest leverage:
quality and performance-per-token across model classes; keep generating
and testing creative hypotheses and adopting successes to no end. ALL
prompt-editing principles MUST HOLD — re-read them. NEVER REWARD HACK.
Think extremely deeply about fundamental (never surface) reasons for
failure; hypotheses must be testable; adopt only what actually helps.
Schedule wakeups so usage renewal auto-continues the work."_
