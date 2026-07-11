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

## 2026-07-09 (route-first / capacity / ownership session)

- **Every server-side validator a model can trip must be STATED in the
  template it gates — invisible floors are the corpus's dominant failure
  class.** All four eval failures triaged today were the same bug wearing
  different clothes: `limits.py` enforced a cap (topic depth 4, intervention
  question ≤ 25 words, route reason ≤ 12 words) or Pydantic demanded a shape
  (plan_revision phases) that the prompt never showed. Codex did the RIGHT
  pedagogy and failed mechanically — the fixes moved scores 0.0→0.83,
  fail→1.0, fail→0.67 with one-line prompt edits. Discipline going forward:
  when adding a limit or schema field, grep the template for it in the same
  commit (prompts.md §7b now models this).
- **Reuse must be enforced mechanically before it is prompted.** Topic
  hygiene had prompt-level "prefer attaching" but nothing stopped a router
  from minting `new_topic` for a path that already exists, a prose leaf, or
  a 6-level nest — and no eval measured reuse-over-create for either router.
  Now: applier rejects (exists→"use attach", `[a-z0-9_]+` leaf, depth cap),
  and the `routing` corpus category benchmarks the semantic half the rails
  can't check. Rails catch what's checkable; benchmarks watch what isn't.
- **Push surfaces get principles, pull surfaces get numbers** (owner ruling,
  capacity channel): the daily-completion message carries no counters — a
  streak number above "come back tomorrow" is chain pressure however gently
  worded — while `dojo stats` (consulted by choice) keeps the derived facts.
  The same shape generalizes: announce-once notices state facts with doors
  (maintain/archive/extend), never scores.

## 2026-07-09 (field-bug session)

- **A path filter must test paths relative to the root it guards, never the
  absolute string.** `sync_index`'s hidden-dir skip (`"/." in root`) matched
  the store's OWN prefix (`~/.local/share` → `.local`), making the entire
  default-location store invisible: every `get()` → None, everything
  downstream of it lying. Tests missed it because pytest tmp dirs contain no
  dot-component — conformance now pins a store rooted under `.local/…`.
  The general form: os.walk filters belong on `dirs[:]` (names inside the
  tree), not on `root` (which embeds where the tree lives).
- **A gate that can destroy working state must separate structural findings
  from advisory ones.** install.sh's doctor gate read a mid-command dirty
  store (a NORMAL awaiting-audit state) as non-compliance and rolled back
  the owner's install — while the owner was mid-`dojo learn`. Doctor now
  exits non-zero only on structural categories; recoverable states render
  as ⚠ advisories. Corollary the same evening: long-lived processes must
  not depend on their install staying on disk — templates now snapshot
  in-process at first render, so an upgrade/uninstall under a running
  conversation can't kill it.
- **"Not found" and "already done" are different facts; a loop that
  `continue`s over both reports success it can't prove.** drain_tasks
  skipped unresolvable task refs silently and returned ok — the crash
  surfaced two frames later as `NoneType.context`. Every honest-degradation
  path needs the distinction pinned.
- **The ratchet writer runs at teardown and believes the card, not the
  asserts.** The first live holdout gate persisted the very 0.0 floor its
  own bootstrap assert refused (session-scoped fixture teardown sees all
  collected scores). Ratchet writers must re-apply acceptance rules at
  write time (`merge_holdout_baseline`: zeros never floor, unknown scenarios
  merge in, existing floors immutable).

## 2026-07-11 — encoding-era session learnings

- **Contamination is contextual, not intentional.** A model cannot firewall
  info in its context window; "read but won't use" doesn't exist. Proven
  live: an IDE-selection relay leaked holdout rows into the working session
  minutes after the rule was written. Remedy: burn + regenerate the exposed
  scenario (the transcript then describes a test that no longer exists).
- **Judge-evidence verbatim checks must decode JSON escapes** — LaTeX/regex
  outputs (`\\[` raw vs `\[` decoded) had every honest judge pass discarded
  as "unproven". Fixed in evidence_haystacks; the discard mechanism itself
  is sound anti-reward-hacking machinery.
- **Single-sample floor bootstraps are noise-prone**: two scenarios floored
  at a lucky 1.0 failed on a DIFFERENT criterion each re-run. Multi-sample
  spread + a different-criterion-each-time signature = variance, not a
  failure mode. Owner-approved floor adjustment with documented notes.
- **Structure models must emit is structure models can corrupt**: plan phase
  numbers were retyped by models yet every consumer reads list position —
  now position-assigned at validation. Generalized owner principle.
- **Reflect variance is an architecture smell**: the mega-task juggles five
  jobs; per-sample criterion-dropping is the measurable symptom (STATE 7d).
- **Reasoning-neutral output anchors**: "return only this JSON" suppressed
  deliberation weak models may need; "your final output is exactly this
  JSON (anything before it is ignored)" tells the extraction truth without
  inviting token burn. Empirical check owed via the Ollama pairs.
