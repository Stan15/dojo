# ADR 010: Harness-First Task Fulfillment (Inversion of the Connector Model)

## Status
Accepted (design phase, 2026-07-07). Supersedes the *mandatory* subprocess-connector
model implied by ADR 003/009; preserves ADR 009's value-injection and single-turn
principles.

## Context
The prototype requires dojo to invoke an AI via a configured subprocess connector.
But the priority deployment is an AI harness (Claude Code, etc.) driving the dojo
CLI — an intelligent model is already in the loop. A mandatory connector then means:
a second model bill, API-key/connector setup before first use (breaking "install the
skill and it just works"), harness permission prompts around subprocess execution,
and an extra failure mode. Model caliber is unknown by design, so whatever fulfills
AI work must be swappable and its output untrusted.

## Decision
Dojo never calls an AI directly. It emits **Task** records — single-turn,
value-injected prompts with a compact output contract — inside its JSON envelopes
and as files under `tasks/`. Fulfillment adapters, all satisfying the same contract:

1. **Host harness inline (default, zero config):** the driving agent fulfills the
   task itself and returns the result via `dojo task submit <id>`.
2. **Subprocess connector (kept, demoted):** `dojo task run` drains pending tasks
   through a configured command — for headless/cron replenishment and non-agent use.
3. **API provider (future, for the app):** same task records, remote fulfiller.

Submission is the only path by which AI output mutates state: Pydantic validation →
typed, idempotent applier per task kind → bounded retries (2) with error feedback →
`failed` + honest degradation. Commands never block on AI; results land when
submitted.

## Consequences
- "Install skill → just works": no keys, no connector config, no daemons.
- One contract, three fulfillers — no special-cased pipelines.
- Weak models can only fail a task, never corrupt state (validation boundary).
- Mid-session AI work (grading) becomes asynchronous by design; envelopes report
  `pending_grade` and sessions continue — an acceptable UX cost for never blocking.
- Connector code (~500 lines) is retained but re-seated on task records.
