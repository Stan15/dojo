# INSIGHTS — append-only, dated

Non-obvious learnings. Newest at the bottom. Never delete; strike through only if disproven (with a dated note).

## 2026-07-07

- **The priority user is an AI harness, which inverts the connector architecture.**
  The prototype has dojo shell out to an LLM subprocess. But when a harness (Claude
  Code etc.) drives dojo, an intelligent model is *already in the loop* — spawning a
  second one duplicates cost, requires API-key config (breaking "install the skill and
  it just works"), and triggers permission prompts. Inversion: dojo emits schema-bound
  task envelopes; the harness fulfills them inline. Subprocess connectors demote to an
  optional headless adapter. (ADR 010.)

- **Weak models follow a concrete example skeleton better than a formal JSON Schema.**
  `model_json_schema()` dumps are several KB and weak models still violate them. A
  literal example JSON with inline field constraints is both cheaper (context tokens)
  and more reliably followed. Formal validation stays in Pydantic at submit time —
  the schema is for the machine, the skeleton is for the model.

- **Mandatory free-form `thinking` fields are a generation-token tax.** The prototype
  requires a `thinking` string in every LLM response to keep reasoning out of data
  columns. It works, but invites unbounded rambling from weak models. Bounded planning
  fields ("`plan`: ≤ 3 sentences") keep the benefit at a fraction of the cost.

- **Scheduling state must attach to stable nodes, not ephemeral items, or it bloats.**
  For generative skills, exercises are disposable (novelty principle, ADR 007) — so
  per-exercise SR state is state for things that will never repeat. Attach memory
  state to the *topic* for skills, to the *exercise* only for static-recall facts.

- **Campaign-level scheduling is an allocation problem, not a memory problem.**
  SM-2/FSRS models a forgetting curve; campaigns don't forget — learners under-attend
  them. What's needed across campaigns is fair, urgency-weighted rotation with atrophy
  pressure and deadline awareness: a deterministic priority score, fully explainable.

- **The path-leak was already a latent bug, not just a smell (2026-07-07, M1 dig).**
  `Attempt.session` stores `"active_session.json"` — a reference that silently goes
  stale the moment the session archives to `archive/sessions/…` — and
  `Attempt.exercise` is built as `exercises/{id}.md` (api.py submit path) while
  `save_exercise` actually writes `{date}_{counter}_{slug}.md`, so attempt refs can
  point at files that never existed. Consumers recover IDs via `Path(ref).stem`,
  compounding the confusion. Validates ADR 011's ID-based refs as a bug fix.

- **Repo drift found during survey (2026-07-07):** `pydantic` is imported throughout
  but absent from `pyproject.toml` dependencies; two ADRs share number 003; README
  says v1.0.0 while pyproject says 0.1.0; `docs/api-specification.md` still documents
  the SQLite era. Tracked in OPEN-PROBLEMS.
