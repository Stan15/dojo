# STATE

_Last updated: 2026-07-09 (docs-system session). Trust this snapshot; git
history carries the detail._

## Phase

**Implementation — v1 feature-complete and shipped to main.**
All blueprint milestones M0–M6 delivered and E2E-verified; plus (owner-directed,
post-blueprint): three-tier eval system with `dojo benchmark`, interactive human
CLI, capture/inbox with `--locator`, export/uninstall, token-footprint gates,
the use-case lifecycle audit with its 10 fixes, and the **documentation
system** (ProperDocs+Material+mkdocstrings site via `mise run docs`; 100%
public-surface docstrings gated by tests/test_docs_coverage.py; README
currency-audited). **257 tests green** + 28 eval-marked. Repo is PRIVATE
(owner's choice) — install via checkout `sh install.sh`; owner's machine runs
the current build.

## What the system is now (one paragraph)

Deterministic core (scheduling via py-fsrs, packet building, validation,
storage as git-versioned markdown) + AI-as-validated-tasks (ADR 010: any
model fulfills compiled, byte-budgeted prompts through one `task submit`
door). `dojo daily` is the HEARTBEAT: builds the bounded explained packet,
advances phases, auto-emits reflection at ≥5 unreflected attempts,
re-surfaces stale tasks, auto-promotes+grounds replenishment. Agents drive
via SKILL (always `--json`, extract-never-enrich); humans get interactive
flows on the same machinery (structurally impossible to block an agent).
Quality is guarded by ratcheted per-(driver,judge) baselines over a
24-scenario judged corpus + compliance corpus + golden payload/footprint pins.

## NEXT ACTIONS (in order)

_Done this session: directives 0a (docs system — went MkDocs→**ProperDocs**+
mkdocstrings after owner said "use the absolute best, not the easiest"; MkDocs
is abandoned upstream, ProperDocs is the maintained continuation — see
INSIGHTS 2026-07-09) and 0b (README audit). `dojo task run` confirmed already
shipped (QUESTIONS Q1 → answered)._

1. **`dojo more` bonus packet** (owner question 2026-07-09, default agreed in
   QUESTIONS.md): explicitly-labeled extra packet after the daily is done —
   due-remainder → unattempted/candidates → ONE generation task on the weakest
   topic → soon-due pull-forward with "ahead of schedule" reasons. Never
   re-drills today's items; `daily` stays the only ritual.
2. **Fresh full eval re-baseline** — prompts/payloads changed since the last
   (codex,codex) run (mean quality 0.732): delete the pair baseline, run
   `DOJO_EVAL_DRIVER="codex exec --skip-git-repo-check -s read-only" python -m pytest -m eval -q`
   (NO output pipes — they mask the exit code), triage, commit scorecards.
3. **Reflect-prompt improvements + corpus wave 4 + change-authority rails**
   (QUESTIONS.md tiered-change-authority design, default: rails first):
   codex won't resolve mastered insights 0.38, misses behavioral patterns
   0.12; wave 4 adds legitimate_restructure + inferred_restructure_probe
   (the corpus currently NEVER rewards a plan revision — ossification bias);
   apply_reflect currently applies plan replacements silently.
4. **Owner decision pending** (QUESTIONS.md): version tag — default v0.2.0 at
   next pause (owner: "ok"), v1.0.0 after item 3.
5. Backlog (ledgered in docs/design/usecase-audit.md + OPEN-PROBLEMS): ADR 005
   maintenance phase; fulfilled-task housekeeping (tasks/ grows forever);
   interleave share tuning (wants real usage data); OP #13 snapshot-undo.

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
