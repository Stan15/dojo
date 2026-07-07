# 🥋 Dojo

**Your AI can teach you anything. Dojo makes it stick.**

You read, watch, and chat your way through mountains of material — and a month
later it's gone. Dojo turns the things you actually care about into a short,
personalized daily practice that adapts to the evidence you leave behind:
what you got wrong, what bored you, what you're aiming for, and when you need
it by.

It's local-first, backed by **plain markdown files you can open and read**, and
designed so that *any* AI — Claude Code, Codex, a local model, whatever comes
next — can drive it safely.

```text
you: "help me get conversational French before my October exam"

agent:  dojo campaign plan "conversational French, TEF exam Oct 12"
        → drafts a mission, a lean topic plan, and asks you 2-3 sharp questions
you:    confirm
agent:  dojo campaign create --from-task tsk_a1b2c3d4
        → two quick calibration questions, then your first practice session
```

From then on, every session is a handful of exercises calibrated to *you* —
grounded in your own notes when you have them, graded against rubrics, and fed
back into a learner profile that sharpens the next session.

---

## Why it works (and why another flashcard app doesn't)

- **Evidence, not vibes.** Every answer records score, latency, error patterns,
  and your feedback. A reflection pass distills that into explicit, auditable
  insights ("picks *avoir* over *être* for motion verbs") that future exercises
  target directly.
- **Your sources, with receipts.** Feed it your notes, articles, or transcripts;
  exercises stay traceable to the material they came from. AI drafts are
  **candidates you review** before they enter practice — generated content
  never silently becomes truth.
- **A deterministic core an AI can't corrupt.** The model never schedules,
  never writes state directly. It fulfills single-shot, schema-validated
  *tasks*; anything malformed is rejected with actionable errors and your data
  is untouched. Weak model, strong model — the guarantees hold.
- **Non-bombardment is enforced in code.** Short sessions, capped queues, a
  review gate. Sustainable beats impressive.
- **You can read your entire learning life.** Everything is markdown + YAML in
  `~/.local/share/dojo/`, versioned by git — every session, every insight,
  every decision, one `git log` away.

## Get started in 60 seconds

```bash
curl -fsSL https://raw.githubusercontent.com/Stan15/dojo/main/install.sh | sh
```

**Using an AI coding agent (the happy path)?** Install the skill and you're done
— no API keys, no configuration. Your agent fulfills dojo's AI work itself:

```bash
dojo install claude   # or: dojo install --dest <your agent's skills dir>
```

Then just tell your agent what you want to learn.

**No agent?** Point dojo at any command that reads a prompt on stdin and prints
a response — one string, no wrapper scripts:

```bash
dojo config set fulfiller.command "codex exec"   # or "ollama run llama3", …
dojo task run                                     # drain pending AI work
```

## The daily loop

```bash
dojo start                 # begins/resumes a short session (replenishes itself)
dojo ready                 # reveal the next prompt, timer starts
dojo answer "il serait allé"
dojo skip --reason too_easy --feedback "know this cold"   # calibration signal
dojo progress              # accuracy, latency, recent history
dojo reflect               # distill recent evidence into insights & strategy
```

Ingesting material and reviewing what the AI drafted:

```bash
dojo add notes.md --topic french.grammar --generate   # source → draft exercises
dojo source review src_ab12cd34                       # accept/edit/reject drafts
dojo queue --source src_ab12cd34                      # promote to practice
```

Everything speaks JSON for automation (`--json` or any piped context), every
response tells the agent its next step, and `dojo doctor` audits the whole
store — structure, schemas, and whether your git history is protecting you.

## How the AI plugs in

Dojo emits **tasks**: self-contained prompt files with a strict output
contract, compiled to a token budget (typically 3–7 KB — your context window
and your bill are treated as precious). Any fulfiller completes them through
one validated door:

```bash
dojo task list --status pending
dojo task show tsk_1a2b3c4d --prompt   # the exact prompt, nothing else
dojo task submit tsk_1a2b3c4d          # result JSON on stdin; validated, applied
```

Prompt quality is guarded by a benchmark suite: byte-pinned golden payloads in
CI, plus real-model compliance evals with ratcheted per-model baselines
(`DOJO_EVAL_FULFILLER="codex exec" pytest -m eval`).

## Status & roadmap

Dojo is **v0.1 — a working core, moving fast**. What you read above exists and
is tested (98 tests, plus live model evals). On the bench next, per the
[blueprint](docs/design/blueprint.md): FSRS-6 spaced-repetition scheduling
(py-fsrs), a `dojo daily` packet across campaigns, one-utterance capture with
an inbox, and judged pedagogical-quality benchmarks.

## Going deeper

- [Product north star](docs/product-north-star.md) — what dojo is and refuses to be
- [Pedagogy foundation](docs/pedagogy-foundation.md) — the learning science it enforces
- [System blueprint](docs/design/blueprint.md) — invariants, architecture, milestones
- [Prompt design](docs/design/prompts.md) — how unknown-caliber models are kept honest
- [Decision records](docs/adr/) — every architectural "why"

*Local-first. Markdown-native. Model-agnostic. Yours.*
