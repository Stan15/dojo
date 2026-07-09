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

## 2026-07-07 — First real Tier-3 run: the eval system audits its own authors
The first (codex,codex) quality run (mean 0.52) split cleanly into three kinds
of findings, and two of them were OURS, not the model's:
- **Scenario bugs**: pure_recall's judge couldn't verify grounding because the
  source facts weren't in scenario_context (the judge sees only context +
  output); too_easy seeded 5/6=0.83 accuracy while the reflect prompt's own
  threshold says raise only >0.85 — codex obeyed the prompt and the rubric
  punished it. Lesson: **rubrics must be checked for coherence against the
  prompts they judge**, and the judge must be given every fact a verdict needs.
- **Prompt weaknesses**: an escape hatch buried in rule 9 loses to an imperative
  TASK line ("draft exactly 3") — the alternative must appear IN the imperative;
  "compress" without a number doesn't compress (codex: 15 topics under a
  2-week deadline).
- **Real model signal** (kept as baseline): codex is excellent at grading
  integrity and preference adherence (1.00), conservative to a fault on state
  changes (won't resolve mastered insights, hesitates to raise difficulty).
Also: judges wrap verbatim quotes in ellipses — evidence matching needs
edge-tolerant comparison or ~15% of honest passes get discarded.

## 2026-07-09 — Docs system: tool choice, ecosystem shift, and the pass-as-audit
- **pdoc was the easy reach, not the best fit.** Dojo's behavior lives in
  docstrings AND ~10 authoritative prose docs; a docstrings-only site
  structurally under-documents it. MkDocs+Material+mkdocstrings renders both
  into one searchable site with zero custom UI. General rule: pdoc when
  docstrings ARE the docs; MkDocs+mkdocstrings when docs = docstrings + prose.
- **MkDocs is abandoned upstream (2026); ProperDocs is the maintained 1.x
  continuation** the plugin ecosystem (gen-files/literate-nav/section-index)
  migrated to; griffe split into griffe(CLI)+griffelib(lib). First contact
  looked EXACTLY like a supply-chain attack: an unknown package advertising
  itself in build output, already installed. The discriminator between
  "typosquat" and "post-cutoff ecosystem event" is convergent evidence the
  package can't control: other trusted packages' live PyPI metadata, upstream
  issue trackers, independent news. Author-email fields prove nothing.
- **A docstring pass is a disguised audit.** Forcing an honest one-sentence
  description of each function surfaced a dead no-op loop (get_source_topics),
  two functions whose source_id argument silently does nothing (candidates
  carry no source provenance), and the apply_reflect consent gap. When you
  can't write an honest docstring, the code is the problem.
- **The coverage gate is what makes generated docs a system** rather than a
  snapshot: tests/test_docs_coverage.py fails on any undocumented public
  symbol AND on placeholder (<4 word) docstrings, so the reference site can't
  silently rot.
