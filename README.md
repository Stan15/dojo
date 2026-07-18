# 🥋 Dojo

**Your AI can teach you anything. Dojo makes it stick.**

You read, watch, and chat your way through mountains of material — and a
month later it's gone. Dojo turns what you actually care about into a short
daily practice, personalized by the evidence you leave behind: what you got
wrong, what bored you, what you're aiming for, and when you need it by.

Local-first. Plain markdown files you can open and read. Driven safely by
*any* AI — Claude Code, Codex, a local model, whatever comes next.

```text
you: "help me get conversational French before my October exam"

agent:  dojo learn "conversational French, TEF exam Oct 12"
        → drafts a mission, a lean topic plan, and asks you 2-3 sharp questions
you:    confirm
agent:  dojo campaign create --from-task tsk_a1b2c3d4
        → two quick calibration questions, then your first practice session
```

> 🎬 *Demo GIF coming — recording script in [docs/demo-shots.md](docs/demo-shots.md).*

---

## Get started in 60 seconds

```bash
curl -fsSL https://raw.githubusercontent.com/Stan15/dojo/main/install.sh | sh
```

Your entire life with dojo is two commands:

```bash
dojo learn "I want to learn Japanese"   # start something — dojo plans it with you
dojo daily                              # a few minutes of practice — the habit
```

**That's the whole product.** Using an AI coding agent? Install the skill
and you're done — no API keys, no configuration; your agent does dojo's AI
work itself:

```bash
dojo install claude   # or: dojo install --dest <your agent's skills dir>
```

No agent? Point dojo at any command that reads stdin and prints a response:
`dojo config set model.command "codex exec"`, then `dojo task run`.
(Prefer to inspect first? Clone and `sh install.sh` — same installer. Local
models, leaving, taking your data: [docs](docs/api-specification.md).)

## Why it works (and why another flashcard app doesn't)

- **Evidence, not vibes.** Every answer records score, latency, error
  patterns, and your feedback — distilled into explicit insights that future
  exercises target.
- **Your sources, with receipts.** Exercises stay traceable to the material
  they came from; AI drafts wait for your review before they become practice.
- **A deterministic core the AI can't corrupt.** Models fulfill
  schema-validated tasks; malformed output is rejected, your data untouched.
  Weak model or strong — the guarantees hold.
- **Non-bombardment enforced in code.** Short sessions, capped queues.
  Sustainable beats impressive.
- **Your entire learning life is readable.** Markdown + YAML, versioned by
  git — open it as an Obsidian vault.

## The learner model — every belief, with receipts

Dojo maintains an explicit model of you, earned from your actual practice —
and you can read it, trace it, and overrule it:

```text
$ dojo insights

french-conversation
  grammar
    ins_a3f21c88_0 grammar.aux_choice_motion — Picks avoir over être for motion verbs in the passé composé.
      4 answer(s) behind it · 6d old · updated 2026-07-16
  process
    ins_c9d04e12_1 process.avoidance_when_unsure — Skips or answers "I give up" rather than attempting when unsure.
      4 answer(s) behind it · 2d old · updated 2026-07-17
  preference
    ins_e5b19f03_2 preference.dialogue_examples — Retains phrases better from short dialogues than isolated vocab.
      2 answer(s) behind it · 9d old · updated 2026-07-11
```

A misconception from graded mistakes; a *behavior* nobody would tell you
about themselves (your skips — and what you type instead of an answer — are
evidence too); a preference inferred from what actually sticks. Every
belief opens into its receipts:

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

Disagree? `dojo insights resolve ins_xxx --because "I know this — I was
rushing"` — your words, stored verbatim, outrank the evidence. And you can
always just *tell* it things: `dojo feedback "these drills read like
riddles"` reaches the next reflection verbatim. "I didn't understand the
question" is treated as a signal about the material, not about you — the
system is benchmarked on telling those apart.

## The daily loop

`dojo daily` is the heartbeat: a short, interleaved packet, calibrated to
your evidence. It also advances phases, triggers reflection, and tops up
material running dry — nothing depends on a command you might forget.

**You're never graded on material nobody taught you.** New material arrives
as a ☆ study card first; a miss on something you were never shown starts
the schedule instead of punishing you.

```bash
dojo daily     # the whole ritual — the one command to remember
dojo why       # "weakest memory here (~38% recall odds) · French: 6 due…"
dojo stats     # retention estimates, due counts, AI token spend
```

Learned something in the wild? `dojo capture "<the thing>"` saves it now,
files it later. Links too: hand your agent a URL and it captures what your
*why* points at, source recorded — dojo itself never fetches (that keeps
the injection surface closed).

## No guilt, by design

Most spaced-repetition tools die of shame: a two-week absence returns 400
overdue reviews and a broken streak. Dojo refuses the mechanic, in code:

- Come back after two weeks → a **sane packet**, not an avalanche.
- **No streaks, no nags, no engagement theater.** Done for today means done.
- Still hungry? `dojo more` says yes only when your 7-day review load can
  afford it — otherwise it shows you the numbers. Never offered, only
  answered.
- Reviews you've outgrown are noise: `dojo topic retire <topic> --because
  "use it daily now"` stops them; `revive` brings them back.

Finished campaigns switch to **maintenance** — memories kept warm, no new
material — until you extend or archive them.

## Practice from anywhere your agent can reach you

Every response is JSON with a `next` hint, so any agent that can reach you
becomes a practice surface — Hermes over Telegram, a scheduled Claude Code
session, whatever you already live in:

```text
you → hermes:  "run my dojo practice every morning at 8 and message me"

08:00, your messenger pings:
hermes:  Morning! 3 prompts today. First (French, weakest memory ~38% odds):
         "Traduisez : She would have come to the party."
you:     elle serait venue à la fête
hermes:  ✓ 2 to go — and done. 2/3 first try, grades explained. 🥋
```

Scheduling is your agent's cron; delivery is its messenger. Dojo stays
local and asleep until called.

## Benchmark your model

How well does *your* model run dojo's pedagogy?

```bash
dojo benchmark -d "codex exec" --detail
```

```text
Overall  ████████░░ 0.84   (79 scenarios)

Category             Score            What it measures
grading-integrity    ██████████ 1.00  grades content, immune to confident nonsense
personalization      █████████░ 0.92  uses the learner's profile, errors, and preferences
meta-learning        ██████░░░░ 0.55  knows when to ask instead of generate
```

Running local? **gemma3:4b** (~3.3 GB) is the smallest model we've measured
as consistently helpful (80%+ of tasks accepted first try; built-in retries
absorb most of the rest). Smaller than ~4B, current models miss the output
contracts too often — but the benchmark measures any model in one command,
so check yours.

## Under the hood, in one paragraph

FSRS-6 spaced repetition (the algorithm behind Anki) for facts; skills
always get *novel* exercises. The scheduler is pure, deterministic code —
no model ever decides what you practice. AI work happens through budgeted,
schema-validated task files (3–7 KB; your context window and bill are
treated as precious). Start at the [system blueprint](docs/design/blueprint.md).

## Status

**A working v1, used daily by its author, moving fast.** Everything above
exists and is tested — 765+ deterministic tests, live-model evals against
ratcheted baselines, and a blind holdout set that keeps the prompts honest.
Next: v1.0.0 (gated on a strict generalization bar), weak-model profiles,
Anki import that honors your existing memory state.

## Going deeper

- [Product north star](docs/product-north-star.md) — what dojo is and refuses to be
- [Pedagogy foundation](docs/pedagogy-foundation.md) — the learning science it enforces
- [System blueprint](docs/design/blueprint.md) — invariants, architecture, the task contract
- [Prompt design](docs/design/prompts.md) — how unknown-caliber models are kept honest
- [Decision records](docs/adr/) — every architectural "why"
- **Docs site** — `pip install -e ".[docs]" && mise run docs-serve`

*Local-first. Markdown-native. Model-agnostic. Yours.*
