# ADR 017: The Encoding Stage and Practice Continuity

## Status
Accepted (2026-07-10). Owner-directed after a live field failure and a
multi-round first-principles design review (owner approved the final shape:
"i agree with everything you said" + lifecycle/holdout additions, same day).

## Context — the field failure

The owner's first real `dojo learn` campaign ("i have terrible memory",
2026-07-10) exposed a structural gap: **dojo had retrieval events but no
encoding events.** Exercises tested a taxonomy no surface had ever presented;
the learner answered *"you never taught me what the failure patterns are"*
(att_7801ae0e) and honest "I don't know"s were recorded as FSRS lapses
(topic difficulty 9.2/10, stability 0.06d — on material never shown).
Reflection *detected* the gap (insight `memory.needs_mechanism_before_labels`)
and asked "want a recap?" — the learner said yes — but no primitive could
fulfill it: the only downstream verb was "generate more exercises."

Root cause, stated once: **the system conflated "not yet retrievable" with
"never encoded."** Retrieval practice strengthens memory traces that exist;
it cannot create the first trace. Exercises were also memoryless of each
other: generation could not see what prior practice had presented, so
practice could not build on prior practice (no "memorize this key → probe
it across days"), and models re-invented content per exercise (nothing real
was ever tested across sessions).

## Decision

Judgment stays in the model pipeline; math and floors stay deterministic
(ADR 012's split, unchanged). Two substrate capabilities plus rails:

### 1. Encoding semantics ("a first-encounter miss is free")

- A **miss on never-encoded material lands as exposure, not lapse**:
  attempts on items/topics with no SR state and `provenance: synthetic`
  that grade below success land with `grader: "exposure"` — the schedule is
  *initialized* (fixed Good; measured: due next session, ~7d after first
  real success), never punished; the attempt is excluded from phase
  accuracy, reflection windows/triggers, stats, and `more`'s weakest-topic
  math; the full model answer is revealed (the encoding event itself).
- **No ceremony**: first encounters run as normal attempts — a learner with
  prior knowledge answers, gets full credit, and the schedule advances
  normally. The invariant constrains what a miss *means*, not what the UX
  does (owner review: forced pretest/study ceremony was rejected as
  patronizing noise).
- `Exercise.provenance` (`synthetic` | `grounded`) distinguishes
  model-invented material from source/capture-grounded material the learner
  has already met in life; grounded items are test-first as today.
  Diagnostics are untouched (calibration is information, never a test).

### 2. `present` — a legal generator move

`GeneratedItem.skill` gains `"present"`: a deliberate encoding event the
model can PLAN (study card: `answer` = the material, `prompt` = the framing
cue). Serving = show both, learner confirms, exposure lands on the topic's
schedule, item is spent. Never graded; no grade task spent. This is how the
pipeline re-encodes a detected gap mid-campaign and how memory-training
campaigns introduce artifacts ("the golden apple key") whose varied probes
follow on later days.

### 3. Practice-history window in generation payloads

Generation payloads gain a byte-capped, topic-scoped, recency-first section
of recent practice (presented content near-verbatim — it is already
word-capped; probes as glimpses; scores; days-ago), labeled as a WINDOW,
not the whole record. This is what lets the JIT pipeline itself plan
sequences that build across days (introduce → varied-cue probes → escalate)
and avoid probing content nothing presented. Wrong assumptions are
structurally cheap (a probe on unseen material is just a free
first-encounter miss) — **guidance is advisory; the structure makes
violations harmless** (model-strength neutrality applied to prompts).
Long-horizon continuity stays where it already lives: insights.

### 4. `knowledge_gap` grading flag

`GradeResult.knowledge_gap: bool` — set when the learner's own answer says
the material was never learned ("I don't know this / nobody showed me").
The attempt records with feedback but lands **no lapse** and is excluded
from accuracy. The two "I don't know"s stay distinguishable by design:
*never-encoded* is the system's fault (re-encode: answer revealed now;
reflection→`targeted_insights`→`present` next cycle); *encoded-then-forgot*
remains a legitimate lapse (Again is the scheduler working).

### 5. Anti-overwhelm rails (encoding creates future review debt)

- Hard per-packet cap (default 2) on encoding-stage items; remaining slots
  serve due reviews only; a short packet is correct, never backfilled.
- Generator guidance: at most one new artifact per run; never introduce new
  material while a presented artifact awaits its first successful retrieval.
- All existing rails unchanged (packet clamp I3, 2-generation-tasks/day,
  queue cap 20, acquisition discipline, `more` debt guard).

### 6. Recall lifecycle — reduce, retire, never balloon

Owner question: *when is something "no longer needs recalling"?*

- **Frequency reduction is emergent, not decided**: FSRS interval growth
  already decays a known card to a few reviews/year. No component "puts a
  card in maintenance" — the schedule IS the maintenance.
- **Retirement is judgment** and belongs to reflection — the one component
  whose job is reading learner evidence. Its 15-attempt window cannot see
  slow patterns, so the core computes a deterministic **trend digest**
  (per-topic lifetime lines: attempts, accuracy by era, latency trend,
  last-miss age, review-load share; byte-capped) into the reflect payload.
  Implicit signals (fluent-fast streaks, too_easy skips, idle), explicit
  signals (learner voice, insight resolves), and time-trends all land in
  one place, and exposure/knowledge_gap attempts are excluded from mastery
  trends by construction (a topic can never look "mastered" off encodings).
- **Execution runs through existing authority lanes**: learner-initiated
  retirement is immediate; reflection-proposed retirement is a minor,
  announced, revertable change — or a *consent question*, which is now
  legal because retirement gives the questions channel a fulfillment path
  (questions the system cannot fulfill remain banned).
- **Content staleness is deliberately human-curated** (medical facts
  change): automated fact-updating is refused (extract-never-enrich; the
  model is not an authority on current truth). Doors: skip verdicts retire
  items; trend digest surfaces retirement candidates.
- Retired topics stop generating dues; `why`/`stats` count them honestly.
- **Phase advancement never cancels reviews** (owner challenged; engineering
  disagreed and owner accepted): maintaining old strengths across phases is
  spaced repetition's purpose. Only *care* exits reviews.

## Rejected alternatives

- **A `retain` exercise kind / artifact-probe lane with `parent_id`** —
  wrong altitude; its two real needs split cleanly: facts-with-value-in-content
  → the existing recall bank (stable cue→answer pairs, per-item FSRS —
  encoding specificity says stable cues deepen one retrieval path, JIT
  probe-scatter never trains recall); capability-with-disposable-material →
  the skill lane + `present` + history window.
- **Tool-calling in the task contract** (model requests enrichment
  mid-task): fulfillers are stateless one-shot CLI invocations — every hop
  replays full context (token multiplication, the opposite of the goal);
  weak models fail loops (breaks model-strength neutrality); dissolves the
  auditable single-shot compile→submit contract. Bounded alternatives
  already exist (validation-rejection resubmission ≤3, intervention /
  questions channels). If evals ever show payload starvation: single-hop
  enrichment task (structured `need` → ONE follow-up task, budget-capped,
  trace-audited). Evidence-gated, not built.
- **Lesson/explainer entities or teaching task kinds** — token spend +
  drift from retention-first; the exercise `answer` is the kernel.
- **Model-controlled spacing** — memory math stays deterministic (I8);
  the model sequences content, the core spaces encounters.
- **Forced pretest/study ceremony on all first encounters** — patronizing
  to learners with prior knowledge; replaced by miss-is-free.

## Evaluation (owner ruling: every pedagogy surface benchmarked)

New visible-corpus categories with ratcheted floors, shipped WITH the
features: present-planning (plans encoding when history is empty; classifies
bank-card vs skill-probe vs present correctly), gap-grading (flag set on
learner-stated never-learned; adversarially NOT set on ordinary wrong
answers — "flag gap to dodge grading" is a reward-hack), history-use
(probes reference actually-presented content), retirement judgment (trend
digest → correct retire/hold calls). Footprint gates and payload goldens as
always. **Holdout enrichment (owner-directed)**: same breadth of the new
skills, different scenarios, authored BLIND by a subagent pipeline from
category names + public contracts only (never the visible scenarios, never
by whoever tunes prompts), holdout stays smaller than visible; floors
bootstrap at the next release gate (one spend; aggregate gap remains the
only consumable bit).

## Consequences

Store contract deltas (fixture round-trips + blueprint §5 same commit):
`Exercise.provenance`, `Attempt.grader` value `"exposure"`,
`GradeResult.knowledge_gap`, `GeneratedItem.skill` value `"present"`,
topic `retired` flag. Blueprint §7 gains the encoding stage and the
per-packet encoding cap. Prompts: history-window + guidance lines
(generate), gap flag (grade), trend digest + retirement + question-
fulfillability rules (reflect) — all budget-gated, stable-prefix-first
(prompt-caching aware; sweep of older templates is ledgered backlog).
