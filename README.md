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

agent:  dojo learn "conversational French, TEF exam Oct 12"
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
git clone https://github.com/Stan15/dojo && cd dojo && sh install.sh
```

(One-liner `curl -fsSL https://raw.githubusercontent.com/Stan15/dojo/main/install.sh | sh`
works once this repo is public.)

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

**Your data travels.** `dojo export <folder>` writes your entire store as a
fresh markdown tree — read entity-by-entity through the storage layer, blind to
the backend, so the same command stays your escape hatch when other storage
backends exist. The export is itself a working dojo store.

**Leaving?** `dojo uninstall <agent>` removes the skill (only if dojo owns it),
`dojo uninstall --self` tells you exactly how to remove the program for your
install method — and your learning data in `~/.local/share/dojo/` is never
touched either way.

## Tell it what you want to learn

With an agent, just say it — "I want to learn X" triggers the skill. Direct:

```bash
dojo learn "conversational Spanish, in-laws visit in December"
#   → routes the goal against your existing campaigns first (cheapest task):
#     a near fit asks ONE question — extend that campaign, or start fresh?
dojo learn extend tsk_xxx        # extend: adds the topic + a plan phase (undoable)
dojo learn new tsk_xxx           # start fresh: full planning task instead
dojo task show tsk_yyy           # review the proposed mission, topics, phases
dojo campaign create --from-task tsk_yyy    # you approve; nothing is created before this
```

(`dojo campaign plan "<goal>"` still plans directly, skipping the router —
same as `dojo learn --new`.)

One-off things you just learned go straight in, from anywhere:

```bash
dojo capture "git log -S counts occurrences, not diff lines" \
     --why "archaeology" --locator "https://git-scm.com/docs/git-log"
dojo inbox                       # see where the AI proposes to file it
dojo inbox confirm cap_xxxx      # you confirm; it becomes practice material
```

The text is durably saved *before* any AI runs; `--why` keeps your own words
as the reason it matters, `--locator` records where it came from. At a
terminal, `dojo capture` routes and confirms in one breath — the proposal
appears and files with a keypress.

## The daily loop

One command is the heartbeat: `dojo daily` doesn't just pick exercises — it
advances campaign phases, auto-triggers reflection once enough unreflected
evidence accumulates, re-surfaces AI tasks left unfinished yesterday, and
requests replenishment for topics running dry. Nothing the learning loop
depends on waits for a command you might forget to run.

**At a terminal, `dojo daily` is the whole ritual**: pending AI work drains
inline with a spinner (via your configured fulfiller), the session runs as one
continuous conversation — answer, `/skip too_easy`, `/quit` to pause — and
free-form answers are graded in a single batch at the end so nothing stalls
your flow. Then a one-screen stats summary.

Agents (and scripts) drive the same loop stepwise:

```bash
dojo daily                 # today's packet: small, interleaved, every pick explained
dojo why                   # "weakest memory here (~38% recall odds) · French: 6 due…"
dojo start --topic french.oral   # targeted manual drill outside the ritual (replenishes itself)
dojo ready                 # reveal the next prompt, timer starts
dojo answer "il serait allé"
dojo skip --reason too_easy --feedback "know this cold"   # calibration signal
dojo stats                 # per-campaign retention estimates, due counts, AI token spend
dojo progress              # accuracy, latency, recent history
dojo reflect               # distill recent evidence into insights & strategy
```

`dojo stats` is the honesty dashboard: estimated recall odds per campaign
(tagged as estimates — scores and counts are records), days idle, and exactly
how many tokens your AI tasks have consumed, by kind.

Want something to show up more? Two honest knobs, not an algorithm guessing:

```bash
dojo campaign boost french 2.0            # this CAMPAIGN surfaces more in packets
dojo campaign topic-boost french french.oral 3.0   # this TOPIC comes due 3x faster
```

Under the hood: FSRS-6 spaced repetition (the algorithm behind Anki, via
py-fsrs) for facts; skills schedule on their topic and always get *novel*
exercises so you learn the skill, not the question. The scheduler is pure,
deterministic code — no model ever decides what you practice.

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

## Benchmark your model

How well does *your* model run dojo's pedagogy? One command answers with a
category-by-category profile — personalization, calibration, planning,
grading integrity, knowing-when-to-ask, domain breadth:

```bash
dojo benchmark --driver "codex exec"               # judge defaults to the driver
dojo benchmark -d "ollama run llama3" -j "codex exec" --detail
```

```text
Overall  ████████░░ 0.84   (28 scenarios)

Category             Score            What it measures
grading-integrity    ██████████ 1.00  grades content, immune to confident nonsense
personalization      █████████░ 0.92  uses the learner's profile, errors, and preferences
meta-learning        ██████░░░░ 0.55  knows when to ask instead of generate
...
Weakest:   meta-learning (0.55) — knows when to ask instead of generate
```

Scores come from hand-crafted scenarios with planted good/bad references that
calibrate the judge before it's trusted, evidence-anchored verdicts, and the
same validators production uses — headline first, `--detail` when you want
per-criterion verdicts. Dev-side, the same corpus runs as ratcheted regression
evals (`DOJO_EVAL_DRIVER="codex exec" pytest -m eval`) so prompt tweaks
can't silently regress.

## Status & roadmap

Dojo is **a working v1 core, moving fast**. Everything you read above exists
and is tested (257 tests, plus live model evals against ratcheted baselines).
On the bench next: sharper reflection prompts against the measured weak spots,
a wider benchmark corpus, consent rails for AI-proposed plan changes (nothing
restructures under your feet), and a `dojo more` bonus packet for the days you
finish and want extra.

## Going deeper

- [Product north star](docs/product-north-star.md) — what dojo is and refuses to be
- [Pedagogy foundation](docs/pedagogy-foundation.md) — the learning science it enforces
- [System blueprint](docs/design/blueprint.md) — invariants, architecture, milestones
- [Prompt design](docs/design/prompts.md) — how unknown-caliber models are kept honest
- [Decision records](docs/adr/) — every architectural "why"
- **Full docs site** — prose docs + generated API reference, one search:
  `pip install -e ".[docs]" && mise run docs-serve`

*Local-first. Markdown-native. Model-agnostic. Yours.*
