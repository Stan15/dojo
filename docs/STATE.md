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

_Also done 2026-07-09 (owner-directed): **plan change authority** shipped —
tasks/authority.py rails (minor-additive auto-apply + snapshot + announce +
`dojo plan revert`; major inferred → proposal for `dojo plan confirm|reject`;
learner-voice evidence fast path incl. diagnostic answers; anti-drip vs the
last CONFIRMED baseline), ReflectResult `questions` channel → diagnostics,
reflect prompt now SHOWS the plan (was blind; footprint 1967→2523B,
deliberate), corpus wave 4 change-authority category (2 scenarios, floors
raised). 283 tests green._

1. **Route-first entry (`dojo learn`)** — owner-directed 2026-07-09, design
   in QUESTIONS.md: goals route against the registry first (extend = minor
   additive plan change under authority), propose_campaign/"no, new" hands
   off to the full plan pipeline; skip when zero campaigns or explicit new.
2. **Capacity channel (supersedes `dojo more`)** — QUESTIONS.md: bounded
   acquisition top-up at session end + global review-debt guard; honest
   refusal with projection; `start --topic` as the debt-free alternative.
3. **Campaign lifecycle: list/show/archive + completion detection** — owner
   question 2026-07-09 (see QUESTIONS.md entry): consent-gated archive,
   deterministic all-phases-done detection, maintenance-vs-archive choice
   (ties to ADR 005 backlog).
4. **Fresh full eval re-baseline** — prompts/payloads changed again (reflect
   +PLAN section): delete the (codex,codex) pair baseline, run
   `DOJO_EVAL_DRIVER="codex exec --skip-git-repo-check -s read-only" python -m pytest -m eval -q`
   (NO output pipes — they mask the exit code), triage, commit scorecards.
   Reflect-prompt iteration against the measured weaknesses (resolve 0.38,
   patterns 0.12) continues against the ratchet; heartbeat-flow scenarios
   still owed for wave 4.
5. **Owner decision pending** (QUESTIONS.md): version tag — default v0.2.0 at
   next pause (owner: "ok"), v1.0.0 after item 4.
6. Backlog (ledgered in docs/design/usecase-audit.md + OPEN-PROBLEMS): ADR 005
   maintenance phase; OP #14 queue-limit archives consolidated memories;
   fulfilled-task housekeeping (tasks/ grows forever); interleave share
   tuning (wants real usage data); OP #13 snapshot-undo.

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
