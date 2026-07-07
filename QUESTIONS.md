# QUESTIONS for the product owner

Non-blocking. Each open question has the default I will proceed on if unanswered.

## Open

1. **Subprocess connectors** (was Q3): keep as secondary adapter behind the task
   contract, or drop until asked for? **Proceeding on default: keep, demoted,
   re-seated on task records (M2).**
   *Elaboration:* today's prototype lets you register an external command as the
   AI (`dojo connect ai command mymodel -- ~/bin/ollama-wrapper.sh`); dojo runs
   that subprocess whenever it needs generation/grading. In the new design
   (ADR 010) your harness — Claude Code etc. — does the AI work itself, so most
   users never need a connector. The question is whether we keep the subprocess
   path for the two agent-less scenarios: (a) headless automation, e.g. a nightly
   cron running `dojo task run` so your queue is replenished before you wake up,
   and (b) plain-CLI users with no harness who want a local model to power
   generation. "Re-seated on task records" means it stops being its own pipeline:
   it just reads the same pending task files and submits through the same
   validated `dojo task submit` path the harness uses — one contract, so it can
   never behave differently from the harness path. Cost of keeping: ~500 lines +
   tests. My default: keep it, because (a) is genuinely useful for a daily-ritual
   product.

## Answered (2026-07-07)

- **Grading source of truth** — AI grades against rubric when a harness is
  present; self-report fallback offline; `dojo correct` overrides. *(agreed)*
- **Daily packet size** — 5 default, hard cap 8, `daily.packet_size` config. *(agreed)*
- **`archived_implementation/`** — stays in-tree for easy reference until the
  owner clears it; excluded from packaging/tests. Blueprint M1 updated.
- **Python floor** — 3.11. *(agreed)*
- **Capture routing** — routes are proposals awaiting **confirmation by default**
  (inline in conversation or via `dojo inbox`); `capture.autofile: true` opts into
  auto-filing. ADR 013 + blueprint §8 updated.
- **SR scheduling library** — reuse over build: **py-fsrs** (MIT, official FSRS-6
  reference impl) behind a dojo-owned boundary. ADR 014.
- **Anki integration** — no live sync (would split scheduling authority and starve
  the evidence loop); deck **import** and one-way **export** are backlog. ADR 015.
