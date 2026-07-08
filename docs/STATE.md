# STATE

_Last updated: 2026-07-07 (session 3)_

## Phase

**Implementation.** M0 ✅ M1 ✅ **M2 ✅ (task contract — the architecture's heart).**
Next: Tier-3 judged evals + wide pedagogical corpus (owner priority), then M3
(pedagogy engine: py-fsrs scheduling, `dojo daily`, packet builder).

## What M2 delivered (all committed, 94 tests green + 4 eval-marked)

- **Task contract end-to-end (ADR 010):** `Task` entity in `tasks/` (prompt as md
  body) → budgeted compiler (`src/dojo/tasks/compiler.py`, I6 byte budgets +
  fulfiller tiers) → `dojo task list/show/submit/run` → validated appliers
  (`src/dojo/tasks/service.py`, I5: salvage → schema → cross-checks → idempotent
  apply; fuzz-pinned state-hash invariance).
- **All five flows rewired, zero blocking on AI:** add-source generation, session
  JIT replenishment (no-session envelope when queue empty), answer grading
  (exact/auto graders deterministic; AI grading = emitted task with verbatim-
  evidence anchor), reflection (insights/strategy/plan under rails), campaign
  planning (`campaign plan` task → `create --from-task` materialization, I2).
- **Prompts as artifacts:** six templates + fragments in `src/dojo/prompts/`,
  strict `render()` (raises on any placeholder problem), `limits.py` as single
  source for every numeric promise, golden byte-pins.
- **Evals (ADR 016):** Tier 1 golden payloads; Tier 2 `pytest -m eval` with
  fulfiller-agnostic runner + ratcheted per-model baselines — **first real
  baseline committed: codex 4/4 scenarios, 100% first-shot compliance, all
  quality signals true.** Tier 3 (LLM-judged pedagogical quality: binary rubric
  criteria, evidence-anchored verdicts, judge calibration gate against planted
  good/bad references, (driver,judge)-pair baselines, longitudinal
  learning-loop scenarios) is DESIGNED in ADR 016 — implementation is the next
  work item, and the owner wants a WIDE, thoughtfully crafted corpus.
- **Legacy deleted** (owner rule: git is the archive): connectors.py,
  generate.py, legacy templates/loader-fallbacks/schemas, connect-ai CLI,
  generation runs, wrapper-script generation. api.py 1810 → 1148 lines.

## Since last update (all committed, 137 tests green + 17 eval-marked)

- **Tier 3 DONE**: judge runner (binary rubrics, verbatim-evidence verdicts,
  calibration gate vs planted references, (driver,judge)-pair baselines with
  margin) + 12-scenario quality corpus across 6 categories (personalization,
  calibration, planning, grading-integrity, meta-learning, domain-breadth),
  including the owner's asks: vague-mission intervention, false-intervention
  control, "improve my memory" plan elucidation, math scaffolding, pure recall.
  Deterministic corpus-integrity tests keep it from rotting in CI.
- **Intervention contract**: generator may return zero items + structured
  intervention (clarify_goal/need_context/scope_too_broad, 1-3 questions);
  applier turns questions into diagnostic exercises; plan prompt got the
  vague-goal rule (9b3ec16).
- **`dojo benchmark` shipped**: eval machinery lives in dojo.evals (corpus as
  package data); category-grouped strength/weakness display, --detail opt-in,
  JSON reports; README documents it (ebfd201, and display visually verified).
- Real (codex,codex) full eval run in flight at session end — commit its
  baselines (evals/baselines/) when it lands; investigate any scenario < 1.0
  compliance or with judge-calibration failures.

## NEXT ACTIONS (in order)

1. Commit real codex baselines from the background eval run (see above).
2. M3 — pedagogy engine (blueprint §10): `fsrs` dep + `src/dojo/scheduling/`
   wrapper (band→Rating per ADR 014); per-item SR on recall exercises + topic
   SR in topics.yaml; score-landing hook (submit_answer/apply_grade/correct →
   scheduling.record_outcome); Tier-1 allocator; pure packet builder (I3/I8
   property tests); `dojo daily` + `dojo why`; offline-floor test (I4).
3. M4 — capture/inbox/route + `dojo capture`; M5 — skill/envelope polish
   (SKILL.md ≤60 lines, `dojo stats`); M6 — real-harness E2E + ship.

## Standing owner directives (beyond blueprint)

- No context bloat; model-strength neutrality (floor-not-ceiling; §1b prompts.md).
- Delete-over-retain (git is the archive). `archived_implementation/` exempt (Q4).
- Prompts live in .md files, value-only `{{ }}` injection.
- Eval system: reproducible, fulfiller-agnostic, (driver,judge)-pair baselines;
  codex locally available for real runs — never hardcoded.
- Maintain README (viral-grade) and this STATE continuously.

## Open questions

QUESTIONS.md Q1 (fulfiller runner) — answered by owner notes + built as designed;
runner shipped as `dojo task run`. No open questions.
