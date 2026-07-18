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

> 🎬 *Demo GIF coming — recording script in [docs/demo-shots.md](docs/demo-shots.md).*

From then on, every session is a handful of exercises calibrated to *you* —
grounded in your own notes when you have them, graded against rubrics, and fed
back into a learner profile that sharpens the next session.

---

## Get started in 60 seconds

```bash
curl -fsSL https://raw.githubusercontent.com/Stan15/dojo/main/install.sh | sh
```

Then your entire life with dojo is two commands:

```bash
dojo learn "I want to learn Japanese"   # start something — dojo plans it with you
dojo daily                              # a few minutes of practice — the habit
```

**That's the whole product.** One command when you want to learn something,
one command you come back to every day. Everything below is why those few
minutes actually stick.

**Using an AI coding agent (the happy path)?** Install the skill and you're done
— no API keys, no configuration. Your agent fulfills dojo's AI work itself:

```bash
dojo install claude   # or: dojo install --dest <your agent's skills dir>
```

Then just tell your agent what you want to learn.

**No agent?** Point dojo at any command that reads a prompt on stdin and prints
a response — one string, no wrapper scripts:

```bash
dojo config set model.command "codex exec"
dojo task run                             # drain pending AI work
```

Running local? Honest, measured guidance: **gemma3:4b** (~3.3 GB) is the
smallest model we've found consistently helpful — over 80% of dojo's AI
tasks accepted first try on our benchmark corpus, and dojo's built-in
retries absorb most of the rest. **qwen3.5:4b** (thinking off) also works,
leaning harder on retries. Below the ~4B class, current models miss dojo's
output contracts too often to recommend as your daily fulfiller — but
`dojo benchmark` measures any model in one command, so check yours.

(Prefer to inspect before piping to `sh`? `git clone
https://github.com/Stan15/dojo && cd dojo && sh install.sh` — same installer.
Local ollama, leaving, or taking your data with you:
[install & data portability](docs/api-specification.md).)

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
  *tasks*; anything malformed is rejected and your data is untouched. Weak
  model, strong model — the guarantees hold.
- **Non-bombardment is enforced in code.** Short sessions, capped queues, a
  review gate. Sustainable beats impressive.
- **You can read your entire learning life.** Everything is markdown + YAML in
  `~/.local/share/dojo/`, versioned by git — open it as an Obsidian vault and
  each campaign reads as a clean note. Machine bookkeeping stays in dot-files
  out of sight.

## The learner model — every belief, with receipts

This is the part no flashcard app has: dojo maintains an explicit model of
you — and **you can read it, trace it, and overrule it**.

```bash
dojo insights                    # every belief the system holds about you
dojo insights show ins_xxx       # the receipts: your verbatim answers behind a belief
dojo insights resolve ins_xxx --because "I know this — I was rushing"
                                 # your words, stored verbatim, outrank the evidence
```

`dojo insights` reads like this — every belief earned from your actual
practice, nothing you had to write down yourself:

```text
french-conversation
  grammar
    ins_a3f21c88_0 grammar.aux_choice_motion — Picks avoir over être for motion verbs in the passé composé.
      4 answer(s) behind it · 6d old · updated 2026-07-16
  process
    ins_c9d04e12_1 process.avoidance_when_unsure — Skips or answers "I give up" rather than attempting when unsure; subjunctive prompts especially.
      4 answer(s) behind it · 2d old · updated 2026-07-17
  preference
    ins_e5b19f03_2 preference.dialogue_examples — Retains phrases better from short dialogues than isolated vocab.
      2 answer(s) behind it · 9d old · updated 2026-07-11

these are plain markdown files under campaigns/*/insights/ — editing them directly is first-class
```

Notice what's in there: a grammar misconception distilled from graded
mistakes, a *behavior* nobody would tell you about themselves — your skips,
and what you type instead of an answer, are evidence too, and dodging
practice when unsure is exactly what kills retention — and a preference
inferred from what actually sticks. Every belief opens into its receipts:

```text
$ dojo insights show ins_a3f21c88_0

grammar.aux_choice_motion (ins_a3f21c88_0, active)
Picks avoir over être for motion verbs in the passé composé.

Why we believe this — your own answers:
  2026-07-14 · Traduisez : She went to the market yesterday.
    › "elle a allé au marché hier" — score 0.3 (graded by ai, aux choice)
  2026-07-16 · Traduisez : We arrived before the rain.
    › "nous avons arrivé avant la pluie" — score 0.3 (graded by ai, aux choice)

Effect: 3 exercise(s) generated to target this (2 in the last 7 days)
```

Future exercises target these beliefs; resolving one redirects your practice
immediately. Your word is always the higher authority: the machine holds
hypotheses, you hold the truth.

Most of the model builds itself from evidence — but you can also just *tell
it things*, and your words are read verbatim by the next reflection:

```bash
dojo feedback "the subjunctive drills read like riddles — I can't tell what's being asked"
dojo skip --feedback "too abstract, give me a concrete sentence to fix"
```

Confusing questions get rewritten, not held against you: "I didn't
understand the question" is a signal about the *material*, and the system
is benchmarked on telling that apart from a knowledge gap.

The same receipts run through everything: `dojo why` explains today's picks
in one sentence each, `dojo stats` tags estimates as estimates, and every
AI-derived score traces back to the model's own words (`dojo task show
--trace`).

## The daily loop

`dojo daily` is the heartbeat: it picks a short, interleaved packet, advances
campaign phases, triggers reflection when enough evidence accumulates, and
tops up material running dry. Nothing the learning loop depends on waits for
a command you might forget.

**You're never graded on material nobody taught you.** Genuinely new material
arrives as a ☆ study card (read it, own it — recall practice follows in later
sessions), and a miss on something you were never shown starts the schedule
instead of punishing you. Real forgetting of things you *were* taught still
counts — that's the scheduler doing its job.

```bash
dojo daily     # the whole ritual — the one command to remember
dojo why       # "weakest memory here (~38% recall odds) · French: 6 due…"
dojo stats     # retention estimates, due counts, AI token spend
```

Inside a session: type your answer, or `/why`, `/back` to amend, `/skip
too_easy`, `/quit`. Through an agent you don't even need these — say "let's
practice" and it runs the same machinery. One-off things you just learned go
straight in from anywhere: `dojo capture "<the thing>"` saves first, files
later. **Links work too**: hand your agent an article or video URL and it
captures the key content using its own access — the link rides along as
provenance (`--locator`), and exercises generated from it stay traceable to
it. (Dojo itself never fetches URLs — your agent's reach is the reach, which
is also what keeps the injection surface closed.) Details:
[capture & inbox](docs/design/blueprint.md).

## No guilt, by design

Most spaced-repetition tools die of shame: a two-week absence returns 400
overdue reviews and a broken streak. Dojo refuses the whole mechanic —
as **policy, enforced in code**:

- Come back after two weeks and you get a **sane packet**, not an avalanche.
  Leaving is a state, not a failure.
- **No streaks, no nags, no engagement theater.** Done for today means done;
  consistency is taught as a principle, never scored over your head.
- Still hungry? `dojo more` grants extra NEW material — but only when your
  projected 7-day review load stays inside capacity. Otherwise it refuses,
  shows you the numbers, and points at a free alternative. It's never
  offered, only answered: dojo doesn't manufacture appetite.
- Reviews you no longer care about are noise: `dojo topic retire <topic>
  --because "use it daily now"` stops them (and `revive` brings them back).

When a campaign's last phase is passed, dojo says so and switches it to
**maintenance**: reviews keep memories warm, no new material — until you
extend or archive it. Want something to show up more? Two honest knobs:
`dojo campaign boost` and `topic-boost`. No algorithm guesses at you.

## Practice from anywhere your agent can reach you

The whole loop is JSON with a `next` hint on every response, so **any agent
with a messenger bridge becomes a practice surface** — tell your assistant to
run `dojo daily` every morning at 8 and your practice arrives as a chat
conversation, graded and explained. Dojo stays local, deterministic, and
asleep until called. Recipe and shot list: [docs/demo-shots.md](docs/demo-shots.md).

## Benchmark your model

How well does *your* model run dojo's pedagogy? One command answers with a
category-by-category profile:

```bash
dojo benchmark -d "codex exec" --detail
```

```text
Overall  ████████░░ 0.84   (28 scenarios)

Category             Score            What it measures
grading-integrity    ██████████ 1.00  grades content, immune to confident nonsense
personalization      █████████░ 0.92  uses the learner's profile, errors, and preferences
meta-learning        ██████░░░░ 0.55  knows when to ask instead of generate
```

Hand-crafted scenarios with planted references calibrate the judge before
it's trusted; a live pane shows the model thinking in real time. Details,
standing judges, and local-model drivers: [prompt design & evals](docs/design/prompts.md).

## Under the hood (one paragraph)

FSRS-6 spaced repetition (the algorithm behind Anki) for facts; skills
schedule on their topic and always get *novel* exercises. The scheduler is
pure, deterministic code — no model ever decides what you practice. AI work
happens through **tasks**: budgeted prompt files (3–7 KB — your context
window and your bill are treated as precious) with strict output contracts,
validated at one door. The curious should start at the
[system blueprint](docs/design/blueprint.md).

## Status & roadmap

Dojo is **a working v1, used daily by its author, moving fast**. Everything
above exists and is tested (760+ deterministic tests, plus live-model evals
against ratcheted baselines and a blind holdout set that keeps the prompts
honest). On the bench: v1.0.0 (gated on a strict prompt-generalization bar),
first-class weak-model profiles, and Anki import that honors your existing
memory state.

## Going deeper

- [Product north star](docs/product-north-star.md) — what dojo is and refuses to be
- [Pedagogy foundation](docs/pedagogy-foundation.md) — the learning science it enforces
- [System blueprint](docs/design/blueprint.md) — invariants, architecture, the task contract
- [Prompt design](docs/design/prompts.md) — how unknown-caliber models are kept honest
- [Decision records](docs/adr/) — every architectural "why"
- **Full docs site** — `pip install -e ".[docs]" && mise run docs-serve`

*Local-first. Markdown-native. Model-agnostic. Yours.*
