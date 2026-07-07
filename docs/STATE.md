# STATE

_Last updated: 2026-07-07 (late session)_

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

## NEXT ACTIONS (in order)

1. **Tier 3 evals + corpus** (todo): implement judge runner per ADR 016 §Tier 3;
   craft the wide scenario corpus stretching pedagogy + personalization
   (recurring-error targeting, skip-signal calibration, deadline compression,
   plateau handling, mastery resolution, preference adherence; longitudinal
   reflect→generate chains). Run real baseline with codex as driver AND judge.
2. README viral-grade rewrite (owner ask) — keep truthful to current surface.
3. M3 — pedagogy engine (blueprint §10): py-fsrs behind `scheduling` boundary,
   topic-level skill SR, Tier-1 allocator, packet builder, `dojo daily`,
   `dojo why`, offline-floor test.
4. M4 — capture/inbox/route + `dojo capture`; M5 — skill/envelope polish (SKILL.md
   ≤60 lines, `dojo stats`); M6 — real-harness E2E + ship.

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
