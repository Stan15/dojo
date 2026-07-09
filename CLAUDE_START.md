# CLAUDE_START — session entry point

Governing method: `/Users/stans/projects/agentic-dev-method/agentic-dev.md` — adopt it
fully. You are the principal engineer of Dojo; the human is the product owner.

Read, in this exact order, nothing else first:

1. `docs/STATE.md` — current phase, what's done, exact next actions. **Trust it; keep it current.**
2. `docs/design/blueprint.md` — the authoritative v1 product & system design. New work
   is checked against this, not re-derived.
3. `docs/OPEN-PROBLEMS.md` and `QUESTIONS.md` — known gaps and pending human decisions
   (each question has a default; proceed on defaults unless answered).

Deep background, only when a task touches it:

- `docs/product-north-star.md`, `docs/pedagogy-foundation.md` — product vision & pedagogy (authoritative).
- `docs/design/prompts.md` — prompt-craft rules + model-strength neutrality; edit
  templates only with this open (goldens + footprint baselines will diff).
- `docs/design/usecase-audit.md` — every user journey traced; the backlog ledger.
- `docs/adr/` — decision records. ADR 010–016 supersede earlier ADRs where they conflict.
- `docs/INSIGHTS.md` — non-obvious learnings; append when you learn something durable.
- `archived_implementation/` — the old SQLite implementation. Mine for lessons; never import from it.
- `docs/ramblings-planning-not-authoritative/` — sketches only, never contracts.

## Test gate (must pass before EVERY commit)

```bash
python -m pytest -q
```

Nothing previously green may go red. Behavioral tests accompany the code they prove,
in the same commit.

Real-model evals (slow, cost money — on demand, never in the default gate):

```bash
DOJO_EVAL_DRIVER="codex exec --skip-git-repo-check -s read-only" python -m pytest -m eval -q
```

Ratcheted baselines live in `evals/baselines/` (per driver__judge pair); a
prompt change that moves scores updates the baseline in the SAME commit.
Never pipe eval runs through `tail` — it masks the exit code.

## Ground rules specific to this repo

- Commit every completed logical unit immediately; conventional messages; never batch.
- Push to origin main when a chunk is done — the owner installs from this repo
  (`sh install.sh` uses the CHECKOUT, uncommitted tree included: never leave it broken).
- The markdown store format is a **public contract** (see blueprint §5) — changes to it
  require a fixture round-trip test and a blueprint update in the same commit.
- Context economy is a tested invariant: compiled AI-task payloads have byte budgets
  asserted in tests. Never grow a prompt or SKILL.md without checking the budget
  (`evals/baselines/token-footprint.json` gates ±5%; deliberate changes update it).
- Two audiences, one guarantee: agents (`--json`) can never hit interactive
  input (tested tripwire); humans get flows in `src/dojo/interactive.py`.
- Docs are generated: `mise run docs` builds the site (ProperDocs — the
  maintained MkDocs continuation, not a typo); every public symbol needs a
  real docstring (tests/test_docs_coverage.py gates it).
- The attack plan is a consent-gated contract (`src/dojo/tasks/authority.py`):
  AI restructures never apply blind — read it before touching apply_reflect.
- The owner reports field bugs from THEIR install mid-session — treat those as
  the highest-signal tests you have.
- An out-of-date `docs/STATE.md` at session end is a bug you introduced.
