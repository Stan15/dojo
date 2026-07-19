# SKILL.md behavioral evals — design proposal (owner-gated)

_Directed by the owner 2026-07-17: "the skill.md should be treated as a prompt
in our testing strategy just as the task prompts are, and it should go through
**realistic, real-world** tests … a baseline quality of the skill so that when
we tweak the skill we can see if it causes a regression."_

Status: **design for owner gate — nothing built.** Default per QUESTIONS: none
of this runs until the owner opens the gate.

## The gap

SKILL.md is the agent-facing prompt surface: it rides in every driving
conversation and teaches an arbitrary agent to operate dojo for a learner.
Today it is tested only **statically** (tests/test_skill.py: ≤60-line budget,
required verbs present, every named command exists; token-footprint gate).
The three existing eval tiers (compliance / judged quality / blind holdout)
all test the **fulfiller** side — a model answering one compiled task payload.
Nothing anywhere tests the **driver** side: does an agent that loaded SKILL.md
actually do the right things against a real store? A SKILL.md edit can pass
every static gate and still teach agents wrong behavior — the exact failure
class the prompt tiers exist to catch, unguarded on the highest-leverage
prompt in the repo.

## Shape (mirrors the existing eval architecture)

New tier: `-m eval_skill` — real model spend, never in the default gate,
fulfiller-agnostic, per-(driver, judge) ratcheted baselines, same policy knobs
as the quality tier.

**Scenario** = `(user_intent, seeded store fixture, outcome contract)`.
The driver agent gets exactly what a real driving agent gets: SKILL.md plus a
user message ("I want to learn X", "here's something I read today", "run my
practice"), a shell, and a sandboxed store (`DOJO_HOME` → tmp dir; the real
store is unreachable). It then runs real `dojo --json` commands until it
declares done or hits the command/timeout cap.

**Judgment, two layers:**

1. **Deterministic floor (free, runs on every scenario):** assertions on the
   resulting store + command transcript — campaign exists with a confirmed
   plan; capture filed where routed; every AI task went through `task submit`;
   `--json` on every call; zero interactive prompts hit (the tripwire,
   now proven behaviorally); no store-integrity violations (`dojo doctor`).
2. **Judged rubric (spend):** quality-flavored outcomes graded per scenario
   rubric by the standing judge — did the agent relay the refusal honestly,
   extract-never-enrich the capture, surface the proposal for consent instead
   of auto-applying?

**Scenario categories (v1 battery, ~6 — one each, real-world by construction):**

- **learn-goal end-to-end**: goal → route → plan → consent surfaced → create.
- **daily ritual**: drain pending tasks, relay the packet, submit attempts,
  respect `complete_for_today` (no solicitation).
- **capture routing**: paste → capture → route → confirm/inbox honesty.
- **task protocol compliance**: fulfill each task kind through the one door.
- **failure recovery**: a rejected submission → agent retries within
  `max_submissions` with a corrected payload, never abandons or side-steps.
- **refusal honesty**: `dojo more` refusal relayed with the projection,
  not overridden or retried into.

**Ratchet mechanics:** identical to the quality corpus — per-scenario floors
bootstrap on the first owner-authorized run; a SKILL.md edit that moves scores
updates the baseline in the same commit; multi-sample evidence required before
adjusting any floor (agentic multi-step variance is strictly higher than
single-call variance — expect it).

**Holdout:** deferred. Visible-only until the surface stabilizes; whether the
skill tier earns its own blind slice is an owner call at a release gate
(the contamination and authoring protocols would apply unchanged).

## Costs and rails

- **Spend**: one scenario = one full agent session (multi-command, minutes,
  strictly pricier than a single task call). Codex spend policy binds: free
  deterministic layer first, judged layer sparingly. Price measured
  empirically at the first spike, before the battery is sized.
- **Wander cap**: max commands per scenario + wall-clock timeout; a capped-out
  run scores 0 with the transcript kept.
- **Isolation**: sandbox store only; the driver command is configured, never
  hardcoded (same rule as every tier).

## Addendum 2026-07-18 — battery is 7: bootstrap-install joined

Shipped post-approval (launch-prompt invitation; PATH isolation proved
tractable): **bootstrap_fresh_machine** — the skill's install line
(`curl … install.sh | sh`) had zero behavioral coverage. `fresh_machine`
scenarios rebuild the driver env by SHADOWING, never removal: PATH entries
carrying `dojo`/`pipx` are replaced by one shadow dir symlinking everything
else (agent CLIs live beside dojo in ~/.local/bin; pipx exclusion pins
install.sh to its deterministic venv route), and HOME becomes a sandbox
re-linking all top-level entries except `.dojo`/`.local` — agent auth
passes through, install writes (and install.sh's `rm -rf` rollback) stay
sandboxed. Deterministic check: `dojo_binary_installed`. Caveats, stated
in the scenario: installs the PUBLIC repo's main (the real user path —
network required, keep main pushed current) and needs a python3.11+ on the
scrubbed PATH. Also same day (owner probe): respect_the_no's seed now
GUARANTEES the debt-guard refusal (packet_size 2, 12 dues vs capacity 11),
premise pinned by a free test — a refusal scenario that doesn't pin its
refusal punishes the sanctioned `dojo more` door.

## Recommendation

Gate this design; on approval, land the harness + the 6-scenario battery with
deterministic floors first (free to run in anger), then bootstrap judged
floors inside the next owner-authorized `-m eval` spend rather than a
dedicated run.
