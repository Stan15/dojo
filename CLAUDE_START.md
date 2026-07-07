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
- `docs/adr/` — decision records. ADR 010–012 supersede earlier ADRs where they conflict.
- `docs/INSIGHTS.md` — non-obvious learnings; append when you learn something durable.
- `archived_implementation/` — the old SQLite implementation. Mine for lessons; never import from it.
- `docs/ramblings-planning-not-authoritative/` — sketches only, never contracts.

## Test gate (must pass before EVERY commit)

```bash
python -m pytest -q
```

Nothing previously green may go red. Behavioral tests accompany the code they prove,
in the same commit.

## Ground rules specific to this repo

- Commit every completed logical unit immediately; conventional messages; never batch.
- The markdown store format is a **public contract** (see blueprint §5) — changes to it
  require a fixture round-trip test and a blueprint update in the same commit.
- Context economy is a tested invariant: compiled AI-task payloads have byte budgets
  asserted in tests. Never grow a prompt or SKILL.md without checking the budget.
- An out-of-date `docs/STATE.md` at session end is a bug you introduced.
