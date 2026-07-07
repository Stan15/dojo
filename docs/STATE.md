# STATE

_Last updated: 2026-07-07_

## Phase

**Design** — complete and awaiting product-owner approval to enter **Implementation**.
The human explicitly gated this transition: do not begin implementation milestones
until they say "continue".

## What exists today (honest inventory)

- **Working-ish prototype**, mid-refactor from SQLite to a git-versioned markdown
  store. Checkpointed at commit `374fd04`.
  - `src/dojo/store/` — new markdown storage engine (frontmatter + body, mtime index,
    file locking, auto git commits). Functional but leaks paths into domain objects.
  - `src/dojo/api.py` — 1,810-line `DojoAPI` monolith holding all business logic.
  - `src/dojo/cli.py` — argparse CLI, `--json` envelopes, installer, doctor.
  - `src/dojo/connectors.py` — subprocess AI connectors (single-turn, value injection).
  - `src/dojo/generate.py` — LLM output salvage parsing + heading-window source slicing.
  - `src/dojo/schemas.py` — Pydantic entities + LLM response schemas.
  - `tests/test_dojo.py` — one consolidated suite, 10 tests, green.
  - `skills/dojo/SKILL.md` — host-agent skill (~78 lines).
- **Strong pedagogy docs** (authoritative): `product-north-star.md`,
  `pedagogy-foundation.md`, ADRs 001–009.
- **Stale docs**: `api-specification.md` and parts of README still describe the SQLite
  era; two ADRs share number 003; `pyproject.toml` is missing the `pydantic` dependency
  it uses; version strings disagree (README 1.0.0 vs pyproject 0.1.0).
- `archived_implementation/` — the pre-refactor SQLite implementation, kept for
  reference only.

## Done this session

- Adopted `agentic-dev-method` (incl. updated §0 philosophy); created scaffolding
  (CLAUDE.md → CLAUDE_START, STATE, INSIGHTS, OPEN-PROBLEMS, QUESTIONS); test gate set.
- Wrote the authoritative v1 design: `docs/design/blueprint.md` — invariants I1–I10,
  correctness arguments for the three compounding zones (scheduler, store
  round-trip, task boundary), milestones M0–M6 with named tests and delegation.
- ADRs 010–013: harness-first task fulfillment (inverts the connector model);
  store protocol with markdown contract; deterministic pedagogy core (Tier-1
  allocation ≠ memory, state on stable nodes); frictionless capture with validated
  routing.
- `docs/design/prompts.md`: all five task prompts crafted for unknown-caliber
  models, with payload byte budgets and the floor-not-ceiling neutrality principle
  (fulfiller profiles scale budgets; bounded note fields as strong-model
  side-channel).
- Product-owner requirements folded in this session: quick capture ("I just
  learned X"), two-tier scheduling, token hyper-awareness, model-strength
  neutrality.

## NEXT ACTIONS (in order)

1. **BLOCKED ON HUMAN**: product owner reviews `docs/design/blueprint.md` +
   `QUESTIONS.md` and opens the implementation gate.
2. Milestone 0 — repo truth pass (fix pyproject deps, renumber ADR 003b, align
   version strings, rewrite stale docs to match the blueprint). Tests: gate stays green.
3. Milestone 1 — domain model + `Store` protocol + `MarkdownStore` conformance suite
   (see blueprint §10 for the full milestone plan and per-milestone test gates).

## Open questions

See `QUESTIONS.md` (all have stated defaults; none block design review).
