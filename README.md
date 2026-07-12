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
  every decision, one `git log` away. The layout is vault-grade: open it as
  an Obsidian vault and each campaign reads as a clean note (mission +
  syllabus), a prose journal, and a hand-editable plan — machine bookkeeping
  stays in dot-files out of sight.

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
dojo config set model.command "codex exec"        # or "ollama run llama3", …
dojo task run                                     # drain pending AI work
```

(Prefer to inspect before piping to `sh`? `git clone
https://github.com/Stan15/dojo && cd dojo && sh install.sh` — same installer.)

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

**You're never graded on material nobody taught you.** Genuinely new
material arrives as a ☆ study card (read it, own it, Enter — recall practice
follows in later sessions, at most two new things per packet), and a miss on
something you were never shown is recorded as a first encounter, not a
failure: the schedule starts instead of punishing, and the full answer
appears on the spot. Real forgetting of things you *were* taught still
counts — that's the scheduler doing its job.

The commands that matter:

```bash
dojo daily     # the whole ritual — the one command to remember
dojo why       # "weakest memory here (~38% recall odds) · French: 6 due…"
dojo stats     # retention estimates, due counts, AI token spend
```

(Inside a session: type your answer, or `/why`, `/skip too_easy`, `/quit`.
Want a targeted extra drill? `dojo start --topic french.conversation`.)

If you talk to dojo *through an agent*, you don't even need these — say
"let's practice" and the agent runs the same machinery stepwise over its JSON
API. It learns how from the installed skill; you never have to.

`dojo stats` is the honesty dashboard: estimated recall odds per campaign
(tagged as estimates — scores and counts are records), days idle, and exactly
how many tokens your AI tasks have consumed, by kind.

### Practice from anywhere your agent can reach you

Dojo never sends messages — but because the whole loop is JSON with a `next`
hint on every response, **any agent that can reach your messenger becomes a
practice surface**. Tell an assistant like Hermes (or any harness with a
Telegram/WhatsApp/Slack bridge) to run your ritual, and your morning looks
like this:

```text
you → hermes:  "run my dojo practice every morning at 8 and message me"

08:00, your messenger pings:
hermes:  Morning! 3 prompts today. First (French, weakest memory ~38% odds):
         "Traduisez : She would have come to the party."
you:     elle serait venue à la fête
hermes:  ✓ 2 more to go. Next: ☆ new material — study this…
         (…finishes the session, then…)
         Done — 2/3 first try, grades explained. Tomorrow makes it stick. 🥋
```

Under the hood that's nothing but the loop above: the agent runs
`dojo daily --json`, relays each prompt verbatim, pipes your replies to
`dojo answer`, and fulfills the AI tasks itself. Scheduling is your agent's
cron; delivery is whatever messenger it already has. Dojo stays local,
deterministic, and asleep until called.

> 🎬 *Demo GIF coming — [shot list](docs/demo-shots.md).*

Want something to show up more? Two honest knobs, not an algorithm guessing:

```bash
dojo campaign boost french 2.0            # this CAMPAIGN surfaces more in packets
dojo campaign topic-boost french french.conversation 3.0   # this TOPIC comes due 3x faster
```

Still hungry after today's session? `dojo more` grants a bounded top-up of
NEW material — but only when your projected 7-day review load stays inside
capacity; otherwise it refuses with the numbers and points you at
`dojo start --topic` (re-drilling costs no new debt). It's never offered,
only answered — dojo doesn't manufacture appetite.

## Your learner model, with receipts

Everything that personalizes your practice is inspectable, traceable, and
contestable — your word always outranks the machine's hypothesis:

```bash
dojo insights                    # every belief the system holds about you, with receipts
dojo insights resolve ins_xxx --because "I know this — I was rushing"
                                 # your words, stored verbatim, outrank the evidence
dojo topic retire aviation.phonetic_alphabet --because "use it daily now"
                                 # reviews you no longer care about are noise — stop them
```

(`dojo insights show` walks any belief back to your verbatim answers;
`dojo topic revive` resumes a retired topic; `dojo campaign list / archive`
manage whole subjects. Git remembers everything you remove.)

When a campaign's last phase is passed, dojo says so and switches it to
**maintenance**: reviews keep coming (memories are kept warm), but no new
material is generated — until you extend it with a new goal or archive it.

Under the hood: FSRS-6 spaced repetition (the algorithm behind Anki, via
py-fsrs) for facts; skills schedule on their topic and always get *novel*
exercises so you learn the skill, not the question. The scheduler is pure,
deterministic code — no model ever decides what you practice.

Have notes or articles? `dojo add notes.md --generate` turns your material
into draft exercises that wait for your review — generated content never
silently becomes practice. And `dojo doctor` audits the whole store whenever
you want reassurance.

## How the AI plugs in

*(Plumbing — your agent handles all of this; shown for the curious.)*

Dojo emits **tasks**: self-contained prompt files with a strict output
contract, compiled to a token budget (typically 3–7 KB — your context window
and your bill are treated as precious). Any fulfiller completes them through
one validated door (`dojo task show` → `dojo task submit`); malformed output
is rejected with actionable errors and your data is untouched. No API keys
live in dojo — the intelligence is whatever you already run.

## Benchmark your model

How well does *your* model run dojo's pedagogy? One command answers with a
category-by-category profile — personalization, calibration, planning,
grading integrity, knowing-when-to-ask, domain breadth:

```bash
dojo benchmark -d "ollama run qwen3:4b"        # grades with your configured judge
dojo benchmark -d "codex exec" --detail        # per-criterion verdicts
```

Set a standing judge once (`dojo config set benchmark.judge "codex exec"`) and
every scorecard is graded by the same referee — comparable across models. In a
terminal you get a **live pane** while it runs: the model's raw stream, its
speed in tokens/sec, and what's being tested, in real time.

> 🎬 *Demo GIF coming — [shot list](docs/demo-shots.md).*

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

Dojo is **a working v1, used daily by its author, moving fast**. Everything
you read above exists and is tested (649 deterministic tests, plus live-model
evals against ratcheted baselines and a blind holdout set that keeps the
prompts honest). Recent: first-encounter teaching (you're never graded on
material nobody showed you), per-topic retirement, an Obsidian-grade store
layout, and the benchmark live pane. On the bench next: v1.0.0 (gated on a
strict prompt-generalization bar), first-class weak-model support profiles
(Raspberry-Pi-class models are being benchmarked now), and decomposing the
biggest AI task into simpler jobs small models handle better.

## Going deeper

- [Product north star](docs/product-north-star.md) — what dojo is and refuses to be
- [Pedagogy foundation](docs/pedagogy-foundation.md) — the learning science it enforces
- [System blueprint](docs/design/blueprint.md) — invariants, architecture, milestones
- [Prompt design](docs/design/prompts.md) — how unknown-caliber models are kept honest
- [Decision records](docs/adr/) — every architectural "why"
- **Full docs site** — prose docs + generated API reference, one search:
  `pip install -e ".[docs]" && mise run docs-serve`

*Local-first. Markdown-native. Model-agnostic. Yours.*
