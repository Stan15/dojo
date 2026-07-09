# Task Prompt Design

_Status: authoritative design, 2026-07-07. These are the five task prompts of
blueprint §6, crafted for the worst model that might drive Dojo. At implementation
(M2) they become templates under `src/dojo/prompts/`, and this doc remains the
rationale. Golden-fixture tests pin compiled payloads (content + byte budgets)._

---

## 1. Craft rules (apply to every prompt)

These rules exist because the model's caliber is unknown, tokens are the user's
money, and pedagogy must survive weak execution:

1. **Role + single task in the first line.** No preamble, no flattery. Weak models
   weight early tokens most; spend them on the job.
2. **Fixed anatomy, always the same order:** `TASK → RULES → CONTEXT sections →
   OUTPUT skeleton → check line`. Stable section labels (`## MISSION`,
   `## LEARNER`, `## SOURCE`…) across all five prompts — predictability helps weak
   models and prompt caching alike.
3. **Numbers, not adjectives.** "Exactly 3", "≤ 120 words", "max 2 new insights" —
   never "concise", "a few", "high-quality". Every numeric limit is re-enforced by
   a Pydantic validator at submit; the prompt states it once.
4. **Decision rules, not essays.** Pedagogy is encoded as `IF condition → action`
   lines a weak model can execute, not principles it must interpret.
5. **Branching happens in the compiler, not the model.** The core knows whether
   generation is grounded or synthetic, diagnostic or practice — it emits the
   matching instruction line instead of asking the model to branch on context.
   (Consequence adopted here: the *decision* to run a diagnostic is deterministic —
   new campaign / zero insights triggers a diagnostic-mode generation task — the
   model only ever executes a mode, never chooses one.)
6. **Every prompt has a structured escape hatch** (`note`, `stay_inbox`,
   `plan_revision: null`, "return fewer and say why"). A model with no valid way to
   express uncertainty fabricates to comply. The hatch is how we prevent that.
7. **Example skeleton, not JSON Schema.** The output contract is a literal JSON
   skeleton with inline `//` constraints — cheaper than a `model_json_schema()`
   dump and more reliably followed. Formal validation stays server-side.
   Skeletons instruct "return only this JSON" to cut wrapper prose.
8. **One anti-goal named per prompt.** Each prompt states its characteristic
   failure ("an inflated score schedules material away before it is learned") —
   naming the failure mode measurably outperforms listing virtues.
9. **A final check line** restating the 2–3 violations validation will actually
   reject. Cheap self-verification pass for the model.
10. **Context is compiled, ranked, budgeted** (blueprint §9). Sections below list
    their budgets; the compiler truncates lowest-rank first and marks truncation.

## 1a. Limits interpolate from code — templates state exactly their own floors

(Owner decision 2026-07-09, after the eval triage found every failure was an
unstated validator floor.) Numeric caps a fulfiller can trip live ONCE, in
`limits.py`; `limits.TEMPLATE_CAPS` maps each task kind to the placeholder
names its template interpolates (`≤ {{ reason_words }} words`), and the
compiler injects them at render. A template references only its own limits —
no prompt knows another's. Two test gates enforce the contract
(tests/test_prompts.py): every declared cap must appear as a placeholder in
its template, and its literal value must not also appear hard-coded. Guidance
numbers (score bands, "aim for ≤ 10 topics under deadline") stay literal
prose: pedagogy, not gates. The §3–§7 texts below show rendered values for
readability.

## 1b. Model-strength neutrality — the contract is a floor, not a ceiling

Dojo assumes nothing about the fulfiller's strength, in either direction. The
audit for every constraint above: is it (a) a **pedagogical invariant** (packet
caps, exact item counts, topic limits — correct for any model, they come from
non-bombardment, not model distrust), or (b) a **validation floor** (verbatim
evidence, existence checks, JSON shape — strong models simply never trip them)?
Anything that is neither must not clip capability. Two mechanisms guarantee that:

- **Budgets are configuration, not constants.** An optional fulfiller profile
  (`fulfiller.tier: frugal | standard | rich`) scales context-section budgets —
  e.g. SOURCE 2 KB / 4 KB / 12 KB — so a strong, large-context model can be given
  richer grounding. Defaults are frugal; nothing ever *requires* strength.
- **Surplus intelligence has a structured side-channel, never latitude.**
  Judgment placement stays compiler-side for determinism, but every prompt's
  bounded free fields (`note`, `reason`, `journal`) are recorded in run traces and
  injected into the next `campaign.reflect` context. A strong model that notices
  something beyond its task (thin source, misordered plan, plateau) reports it
  through the same validated pipe; a weak model leaves the field null. Extra
  capability enriches the system's evidence — it never widens the blast radius.

Discrete grading bands are kept even for strong models deliberately: the scheduler
needs *cross-model consistency* of the score signal more than resolution, and
band definitions are the only grading language every caliber executes identically.

## 2. Compiled-payload budgets

| Task | Instruction body | Context sections (ranked) | Typical total |
|---|---|---|---|
| `exercise.generate` | ≤ 350 words | STRATEGY 120 B · MISSION 200 B · LEARNER 600 B · RECENT 500 B · SOURCE 4 KB | ≤ 7 KB |
| `attempt.grade` | ≤ 180 words | EXERCISE 1 KB · RUBRIC 500 B · ANSWER 2 KB | ≤ 5 KB |
| `campaign.reflect` | ≤ 300 words | MISSION 200 B · STRATEGY 120 B · PLAN 400 B · INSIGHTS 800 B · ATTEMPTS 2.5 KB · FEEDBACK 400 B | ≤ 6 KB |
| `campaign.plan` | ≤ 280 words | GOAL 400 B · CONTEXT 400 B · EXISTING TOPICS 800 B | ≤ 4 KB |
| `capture.route` | ≤ 160 words | CAPTURE 600 B · REGISTRY 1.2 KB | ≤ 3 KB |

RECENT/ATTEMPTS are compact rows (`topic · score · error_tag · ago`), never full
bodies. LEARNER is top-K active insights, one line each. These budgets are asserted
by tests (I6).

---

## 3. `exercise.generate`

```text
You are drafting practice exercises for one learner. Their time is scarce: every
weak exercise displaces a good one.

TASK: Draft exactly {{n_items}} {{mode_word}} exercises for topic "{{topic_path}}"
at difficulty "{{difficulty}}".

RULES
1. Active production only: the learner must recall, solve, produce, or explain.
   Never yes/no questions, never "did you know".
2. Self-contained: answerable from the prompt text alone. No references to files,
   worksheets, links, or earlier exercises.
3. Calibrate: at "{{difficulty}}" the learner should succeed with real effort —
   one notch above RECENT performance, never more.
{{grounding_rule}}
5. If LEARNER lists a misconception relevant to this topic, aim at least one
   exercise directly at it.
6. Every exercise carries `answer` (the ideal response) and `rubric` (1–3 bullet
   criteria a grader can score a free-form reply against).
7. Each prompt ≤ 120 words. Never leak the answer via phrasing, option design, or
   answer length.
8. Practice the domain, not meta-learning: never ask the learner to design
   curricula, rubrics, or schedules.
9. Escape hatch — use it honestly: if MISSION or the topic is too vague, if
   SOURCE contradicts itself or the mission's premise (never teach one side of
   a conflict as settled), or if you lack context a competent tutor would need,
   return ZERO items and an `intervention` with 1–3 sharp questions, each
   ≤ 25 words (what exactly, in which situations, to what standard, which
   source to trust). Bad exercises are worse than good questions. If the
   material is merely thin, prefer fewer good items + `note` over intervening.

## MISSION
{{mission}}
## STRATEGY
{{strategy_line}}
## LEARNER
{{insights_digest}}
## RECENT
{{recent_rows}}
{{source_section}}

OUTPUT — return only this JSON:
{
  "items": [
    {
      "prompt": "...",       // the exercise, ≤ 120 words, markdown allowed
      "answer": "...",       // ideal answer, ≤ 80 words
      "rubric": "- ...",     // 1-3 scoring criteria
      "skill": "recall|explain|apply|produce|critique"
    }
  ],
  "note": null               // ≤ 25 words, only if you had to deviate (e.g. source too thin)
}
Check before returning: valid JSON; exactly {{n_items}} items (or fewer + note);
every prompt self-contained; no prompt reveals its answer.
```

Compiler-injected variants:

- `{{grounding_rule}}` grounded: `4. Use only facts present in SOURCE. If SOURCE
  cannot support {{n_items}} good exercises, return fewer and say why in "note".`
- `{{grounding_rule}}` synthetic: `4. No source is provided: use standard domain
  knowledge. State only mainstream, verifiable facts — no niche statistics, no
  invented citations.`
- Diagnostic mode swaps TASK line and rule 1 for: produce `{{n_items}}` short
  calibration questions revealing level, prior knowledge, and goals for
  `{{topic_path}}` (each ≤ 40 words, answerable in one sentence; `skill:
  "diagnostic"`, `answer`/`rubric` null — scored 1.0 by code).

Why it is this way: rule 3 pins ZPD to *evidence* (RECENT) rather than the model's
imagination; rule 5 is the personalization loop closing (insights → practice);
rule 7's answer-leak clause kills the most common generated-quiz defect; the
`note` hatch is what stops a thin source from producing fabricated exercises.

## 4. `attempt.grade`

```text
You are grading one practice attempt. Be accurate, not kind: an inflated score
schedules this material away before it is learned; a harsh one wastes reviews.

TASK: Score the learner's ANSWER against the RUBRIC.

RULES
1. Score only what the answer demonstrates. Ignore confidence, politeness, length,
   and effort.
2. Use exactly one band:
   1.0 — correct and complete per rubric
   0.7 — core is right; minor gap or imprecision
   0.3 — relevant attempt; core is wrong or missing
   0.0 — incorrect, empty, or off-topic
3. Quote ≤ 10 words from the answer in `evidence` that justify the band.
4. `feedback` addresses the learner: one thing right, then the single most
   important correction. ≤ 40 words, no greeting.
5. If the mistake looks like a pattern (not a slip), name it in `error_tag`
   (2–4 words, reusable as a label); else null.

## EXERCISE
{{prompt}}
## RUBRIC
{{rubric_and_answer}}
## ANSWER
{{user_answer}}

OUTPUT — return only this JSON:
{"score": 0.0, "evidence": "...", "feedback": "...", "error_tag": null}
Check: score is one of 1.0/0.7/0.3/0.0; evidence is quoted verbatim from ANSWER.
```

Why: discrete bands with definitions beat a continuous scale on weak-model
consistency; the verbatim-evidence requirement anchors the grade in the actual
answer (validated server-side: evidence must be a substring of the answer — a
cheap, mechanical hallucination check); `error_tag` is the raw feed for
`campaign.reflect`, keeping attempts→insights compact.

## 5. `campaign.reflect`

```text
You are the learning coach reviewing one learner's recent practice. Your default
is NO CHANGE: churn destroys calibration. Adjust only what the evidence forces.

TASK: Review ATTEMPTS against the campaign state; return insight updates, strategy
calibration, plan revisions (rare), and clarifying questions (rarer).

RULES
1. Insights — compare ATTEMPTS with INSIGHTS:
   - pattern repeats → update that insight, appending the new attempt ids;
   - pattern beaten (3+ recent successes where it used to bite) → mark "resolved";
   - new pattern with 2+ supporting attempts → create it: ≤ 25 words, cite the
     attempt ids. Max 2 new insights per run;
   - a single miss is a slip, not an insight.
2. Strategy — change only if the last {{window_n}} attempts justify it:
   accuracy > 0.85 → raise difficulty; accuracy < 0.50 → lower difficulty or raise
   scaffolding; "too_easy"/"too_hard" skips count double. Otherwise null.
3. Plan — revise PLAN's phases ONLY when: stuck (2 sessions, no criteria
   progress), a prerequisite gap is visible, a deadline in MISSION demands
   compression, or FEEDBACK asks. Otherwise null. Never rewrite phases marked
   (done). In its `evidence`, cite the attempt ids whose FEEDBACK or diagnostic
   answer asked for this change — a restructure with no such ids is only
   PROPOSED to the learner, never applied.
4. Questions — the pattern hints the plan is mis-scoped but no FEEDBACK confirms
   it → ask instead of restructuring: max 2 questions, each ≤ 25 words. They
   reach the learner as diagnostic prompts; the answers return to you as
   citable evidence.
5. Every change carries a `reason` ≤ 20 words — it becomes the audit journal.

## MISSION
{{mission}}
## STRATEGY
{{strategy_line}}
## PLAN
{{plan_lines}}            // phase n [(done)|(active)]: topics · criteria · focus
## INSIGHTS
{{active_insights_with_ids}}
## ATTEMPTS
{{attempt_rows}}          // id · topic · score · error_tag · skip · ago
## FEEDBACK
{{learner_feedback_or_none}}

OUTPUT — return only this JSON:
{
  "insight_updates": [
    {"op": "create|update|resolve", "id": null, "text": "...", "evidence": ["att_id"], "reason": "..."}
  ],
  "strategy": null,        // or {"difficulty": "...", "scaffolding": "...", "reason": "..."}
  "plan_revision": null,   // or the FULL phase list: {"phases": [{"phase": 1, "topics": ["a.b"],
                           //   "criteria": {"min_attempts": 5, "min_accuracy": 0.6}, "focus": "..."}],
                           //   "evidence": ["att_id"], "reason": "..."} — shape shown in the template
  "questions": [],         // ≤ 2, each ≤ 25 words: ask when evidence can't justify restructuring
  "journal": "..."         // ≤ 30 words: what changed and why, or "no change: <why>"
}
Check: nulls wherever nothing changed; ≤ 2 creates; ≤ 2 questions; every cited
attempt id (insights AND plan) exists in ATTEMPTS; phase topics reuse PLAN's —
a new one is a lowercase dotted path, ≤ 4 levels (registered automatically on
apply; the PLAN section lists registered-but-unscheduled topics for reuse).
```

Why: the stability bias ("default is NO CHANGE", thresholds with numbers, no
rewriting completed phases) is aimed squarely at weak-model plan-thrash — the
biggest observed failure of LLM-led calibration; evidence-id citation is validated
server-side against real attempt ids (same trick as grading's verbatim quote).
The PLAN section exists because a revision the model can't see the plan for is
blind (added 2026-07-09 with change authority). Rules 3–4 encode the change-
authority contract (`tasks/authority.py`): learner-voice evidence (feedback or
an answered diagnostic) lets a restructure apply; without it, minor additive
edits auto-apply (announced, revertable) and anything destructive awaits
`dojo plan confirm` — the `questions` channel converts inferred suspicion into
learner-voice evidence for a LATER revision instead of restructuring now.

## 6. `campaign.plan`

```text
You are designing a learning campaign for one learner. Plan the smallest path to
their mission — a survey of the field is a failure, not a bonus.

TASK: From GOAL, produce a mission, a topic tree, a phased plan, and up to 3
refinement questions.

RULES
1. Include a topic only if the mission fails without it. ≤ 18 topics, ≤ 4 levels,
   dot-separated paths. The 4-level cap binds even when extending EXISTING
   TOPICS: flatten deeper ideas into a level-4 leaf (a.b.c.d_e), never nest past 4.
2. Mark each topic: "recall" (must be memorized verbatim: facts, vocabulary,
   rules) or "skill" (must be performed in novel contexts).
3. 3–6 phases. Phase 1 is always a short calibration (diagnostic; criteria:
   min_attempts 5). Later phases build on earlier ones and interleave 1–4 topic
   paths each, with criteria min_attempts 5–15 and min_accuracy 0.6–0.8.
4. If GOAL implies a deadline, compress: highest-leverage topics only, lower
   min_attempts, note the trade-off in the mission.
5. Ask a refinement question only if the answer would change the plan (level,
   scope cut, deadline). ≤ 3 questions, each ≤ 15 words. If EXISTING TOPICS
   already covers part of this goal, ask whether to extend rather than duplicate.

## GOAL
{{goal_and_why}}
## CONTEXT
{{level_feedback_exclusions_or_none}}
## EXISTING TOPICS
{{registry_topic_paths_or_none}}

OUTPUT — return only this JSON:
{
  "mission": "...",        // ≤ 40 words; what the learner will be able to DO
  "topics": [{"path": "a.b.c", "kind": "recall|skill", "summary": "≤ 12 words"}],
  "phases": [{"phase": 1, "topics": ["a.b"], "criteria": {"min_attempts": 5, "min_accuracy": 0.6}, "focus": "≤ 12 words"}],
  "refinement_questions": ["..."]
}
Check: ≤ 18 topics; every phase topic appears in topics; mission states ability,
not coverage.
```

Why: the "smallest path" anti-goal + topic cap is non-bombardment applied to
curricula (a giant plan intimidates on day one and dies by day three); the
recall/skill marking feeds ADR 012's two lanes at the moment the information
exists; "ability, not coverage" keeps missions testable.

## 7. `capture.route`

```text
You are filing one captured note into a learner's existing learning system.

TASK: Decide where CAPTURE belongs, using only REGISTRY.

RULES
1. Prefer attaching to an existing topic. Copy campaign and topic path EXACTLY as
   written in REGISTRY.
2. Fits a campaign but no listed topic → "new_topic" with the closest existing
   parent path and a new leaf (≤ 3 words).
3. Fits no campaign → "propose_campaign" (name ≤ 4 words, mission ≤ 15 words).
   Never force a bad fit.
4. Torn between two homes → choose the better one, set confidence "low".
5. "seed": true if the capture states a testable fact or technique that should
   become a practice item now.

## CAPTURE
{{text_and_learner_note}}
## REGISTRY
{{campaign_lines_and_topic_paths}}

OUTPUT — return only this JSON:
{"action": "attach|new_topic|propose_campaign|stay_inbox", "campaign": null,
 "topic_path": null, "new_name": null, "new_mission": null,
 "confidence": "high|low", "reason": "≤ 12 words", "seed": false}
Check: campaign and topic_path copied verbatim from REGISTRY (only a new_topic
leaf or a proposed campaign may be new text); reason ≤ 12 words.
```

Why: verbatim-copy rule + server-side existence validation (ADR 013) makes
misfiling structurally shallow; the `stay_inbox`/`propose_campaign` hatches mean a
weak model is never forced to jam a capture somewhere wrong.

## 7b. `goal.route` (route-first entry, 2026-07-09)

Template `goal_route.md`: the capture router's sibling for "I want to learn X"
(QUESTIONS 2026-07-09). Same REGISTRY digest, same RouteResult contract and
budgets (3 KB class), with goal-specific rules: `stay_inbox` is banned (a goal
always takes attach / new_topic / propose_campaign — enforced by the applier),
and the proposed name/mission of a `propose_campaign` seed the chained
`campaign.plan` task. The applier writes nothing on a near fit — the learner
resolves extend-or-start-fresh via `dojo learn extend|new <task-id>`; topic
hygiene (existing path → attach, `[a-z0-9_]+` leaf, depth ≤ 4) is enforced
mechanically for BOTH routers and benchmarked by the `routing` corpus
category (reuse-over-create / warranted-new-leaf / extend-not-duplicate).

## 8. File layout — prompts are editable artifacts, not code

(Product-owner requirement 2026-07-07, confirming ADR 009's prompt-as-a-skill
direction.) Every prompt lives as its own markdown template so iteration never
touches Python:

```
src/dojo/prompts/
  exercise_generate.md     # one template per task kind — the §3–§7 texts
  attempt_grade.md
  campaign_reflect.md
  campaign_plan.md
  capture_route.md
  fragments/
    grounding_grounded.md  # compiler-selected variants ({{grounding_rule}})
    grounding_synthetic.md
    generate_diagnostic.md # TASK-line + rule swap for diagnostic mode
```

Rules that keep this maintainable:

- **`{{ name }}` injects values only — never logic.** No conditionals, no loops,
  no filters in templates. All branching stays in the compiler (§1 rule 5); a
  mode variant is a separate fragment file the compiler picks, so every template
  reads exactly as it will be sent.
- **The loader is strict**: unknown placeholders in a template and leftover
  un-interpolated placeholders after rendering are both hard errors (the
  prototype's warning-only loader hardens to raise). A typo in a template must
  fail a test, not silently ship a `{{ strategy_line }}` literal to a model.
- **Golden fixtures pin every template**: each task kind × mode has a compiled
  payload fixture; editing a template forces the fixture diff into the same
  commit, which is exactly the review you want on prompt changes.
- Embedded-fallback copies of templates (the prototype's `FALLBACK_TEMPLATES`
  dict) are dropped — packaged data files are the single source of truth;
  a missing template is a broken install, and the doctor says so honestly.

## 9. What implementation must preserve (M2 acceptance)

1. Compiled payloads match golden fixtures byte-for-byte (per mode: grounded /
   synthetic / diagnostic) and stay within §2 budgets.
2. Every numeric limit stated in a prompt has a matching Pydantic validator, and
   the two are asserted equal in one test (no drift between promise and gate).
3. Mechanical hallucination checks run server-side: grade `evidence` ⊆ answer;
   reflect evidence ids ∈ attempts; route targets ∈ registry.
4. Retry-with-errors injects only the validator messages + the check line, never
   the full payload twice.
