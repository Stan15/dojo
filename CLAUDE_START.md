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
  Numeric caps interpolate from `limits.TEMPLATE_CAPS` ({{ placeholders }},
  single source; drift gates in tests/test_prompts.py) — every validator a
  payload can trip MUST be stated in its template, same commit.
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

**HOLDOUT (absolute owner ruling): NEVER optimize prompts on holdout-set
data** — no verdicts, no traces, no per-scenario peeking, ever. The holdout
(`corpus/holdout/`, `-m eval_holdout`) yields ONE consumable bit: the
aggregate gap vs the visible mean. Bad gap → broaden the VISIBLE corpus and
iterate there. Full protocol: tests/test_evals_holdout.py (its report
mechanically withholds everything but bare scores). Holdout scenarios are
authored by subagents/codex pipelines and never read by whoever tunes prompts.

Run the holdout gate (RELEASE GATES ONLY — before a version tag, after an
iteration series; never mid-iteration):

```bash
# ratcheting release gate (writes/checks the __holdout baseline, prints the gap):
DOJO_EVAL_DRIVER="codex exec --skip-git-repo-check -s read-only" python -m pytest -m eval_holdout -q
# or the aggregate-only report with computed gap + verdict:
dojo benchmark "codex exec --skip-git-repo-check -s read-only" --holdout
```

Both print: holdout mean · visible mean · gap. Gap ≤ 0.1 = prompts
generalize (v1.0.0 tag bar: ≤ 0.1 STRICT — owner ruling 2026-07-10);
> 0.2 = overfit (broaden the visible corpus).

**Holdout AUTHORING protocol (owner ruling 2026-07-10):** enrichment for new
feature surfaces is allowed, with strict ordering — ALL prompt work first,
then holdout, never back with holdout in context. Author via a COLD-context
subagent (or a dedicated fresh session — equivalent isolation; the brief
discipline is what protects, not the vehicle). The brief may contain ONLY:
category/skill names + pointers to public contracts (ADRs, schemas.py,
limits.py, prompt templates, existing holdout dir for FORMAT). It must bar
the author from reading `src/dojo/evals/corpus/quality/` (else holdout
mirrors the visible set). The author reports back ONLY filenames, counts,
and shape-suite results — scenario content never enters a prompt-tuning
context. Holdout stays smaller than visible; floors bootstrap at gates.

**Contamination is contextual, not intentional (owner ruling 2026-07-11):**
a model cannot firewall information inside its own context window —
anything present influences every subsequent output, regardless of intent
or instruction. Therefore: holdout content must NEVER enter the context of
any session/agent that does prompt work — "I read it but won't use it"
does not exist. If holdout content lands in a prompt-work context by ANY
route (accidental file read, a paste, a verbose tool result), that context
is permanently disqualified from prompt work: stop, note it in STATE, and
hand prompt work to a fresh session. This binds humans relaying content
too: quoting holdout material into a working session contaminates it.

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
