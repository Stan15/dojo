# STATE

_Last updated: 2026-07-07 (session 3)_

## Phase

**Implementation.** M0–M3 ✅ · Tier-3 evals + `dojo benchmark` ✅ · corpus
wave 3 ✅ (23 scenarios, ratcheted coverage floors) · **M4 core ✅ (capture/
inbox/route)** · M5 mostly ✅ (SKILL rewritten + tested; `dojo stats` still
open) · token-footprint regression + benchmark context-economy ✅. Pushed to
github.com/Stan15/dojo main (owner installs via curl).

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

## M3 delivered (167 tests green; commits 1df00c1…5b7cad0)

- `dojo/scheduling.py`: py-fsrs behind the boundary (band→Rating per ADR 014,
  injected clock, YAML-safe sr dicts, retrievability).
- `dojo/outcomes.py`: ONE lane-aware landing — recall→item FSRS, skill→topic
  FSRS + item retires 'spent' — called from answers, AI grades, corrections
  (OP #13: additional-review semantics), calibration skips. Diagnostics never
  become memories.
- `dojo/packet.py`: pure seeded builder — Tier-1 (due+atrophy × priority_weight),
  interleaving, weakest/maintenance/frontier mix, skill-stock generation
  requests, honest overflow counts; property tests pin I3/I8.
- Owner's priority knobs (2026-07-07 ask): `dojo campaign boost <id> <f>` =
  cross-campaign surfacing; `dojo campaign topic-boost <id> <path> <f>` =
  intra-campaign emphasis (due-cycle ÷ factor); both visible in `dojo why`.
  Conversational disambiguation guidance goes into SKILL.md at M5.
- `dojo daily` / `dojo why`; offline floor (I4) proven end-to-end.
- Second codex quality baseline: mean 0.646 (from 0.52 after prompt fixes).

## Since M3 (all committed AND PUSHED, 220 tests green)

- Corpus wave 3: 23 quality scenarios / 6 categories / 17 domains; coverage
  floors are ratcheted tests; implicit-ease detection scenario (owner q:
  pattern-based too-easy/hard detection — yes, plus explicit skips as the
  strongest signal). Integrity harness caught topic-depth-3 blocking namespace
  extension (raised to 4 coherently).
- FSRS fuzzing was ON by default (global random ⇒ I8 violation) — caught as a
  test flake, disabled forever, pinned.
- M4: dojo capture / inbox (confirm|dismiss) / route applier with registry
  validation; confirm-by-default (Q6), capture.autofile opt-in; filing turns
  captures into ordinary Sources; daily nags about waiting captures. 9 tests.
- M5: SKILL.md rewritten (≤60-line budget test + anti-staleness test that
  immediately caught `dojo reflect` never existing as a verb — added). Boost
  disambiguation + intervention relay included.
- Fresh-install verification caught the store-birth deadlock (doctor flagged
  its own init forever); stores now born committed, audit commits carry
  identity fallback. Install verified end-to-end in a clean venv.
- Token footprint (owner ask): committed per-kind payload baseline ±5% CI gate
  (evals/baselines/token-footprint.json; generate ≈680 tokens, skill ≈700);
  `dojo benchmark` now reports measured context economy (tokens in/out per task).
- One honest gate violation: pushed once with a red conformance test (birth-
  commit count); fixed in the next commit.

## NEXT ACTIONS (in order)

1. **Background eval run lands** → commit fresh (codex,codex) baselines incl.
   wave-3 scenarios; triage insight_targeting calibration if still failing.
2. `dojo stats` (last M5 item): retention/atrophy + token telemetry surfaces.
3. M6 — drive the real loop from a real harness session (capture → route →
   daily → answer → grade → reflect), LOOK at artifacts, docs truth pass
   (api-specification rewrite), ship v1.
4. Corpus wave 4 (owner: "serious corpus… varied"): ~15 new scenarios —
   domains: music, chess, writing, law, code, poetry-verbatim, numeric-tolerance
   math; signals: too_hard response, overconfident-fast-wrong, atrophy re-entry,
   extend-don't-duplicate planning, unrealistic-timeline honesty, terse-but-
   correct + hedged-but-right grading, contradictory-source intervention,
   text-medium honesty for motor/listening skills. PLUS a coverage meta-test
   (≥N per category, ≥M domains) so corpus breadth is a ratcheted invariant.
2. Eval artifacts: multiline evidence quotes discarded (preference_adherence
   0.14 artifact); insight_targeting judge calibration failing twice — diagnose
   (add verdict detail to gate message), fix, fresh baseline run.
3. M4 — capture/inbox/route + `dojo capture`; M5 — SKILL.md ≤60 lines rewrite
   (incl. boost disambiguation + intervention handling), `dojo stats`; M6 —
   real-harness E2E + ship v1.

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
