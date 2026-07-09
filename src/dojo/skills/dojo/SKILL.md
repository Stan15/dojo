---
name: dojo
description: "Daily learning practice engine. Use when the user wants to learn/study/practice/memorize a topic or skill, says 'quiz me' or 'train me', wants to remember something they just learned ('TIL', 'remember this'), or asks about their learning progress. Knowledge/learning contexts only, not physical workouts."
metadata:
  owner: github.com/Stan15/dojo
---

# Dojo

Local learning engine. **ALWAYS pass `--json` on every command** — without it,
interactive human flows may open and block forever on an agent.

## Two iron rules

1. **`--json`, always** (see above).
2. **Extract, never enrich.** The system learns about the user THROUGH you: pass on
   their goals, deadlines, reasons, and answers in their own words. Do not add
   details, levels, deadlines, or motivations they didn't state — if context is
   missing, the system's own questions (refinements, diagnostics, interventions) will
   ask; relay those and return the user's verbatim answers.

## The task protocol

Envelopes may contain `tasks` — AI work **you** perform, now, in this turn:
1. `dojo task show <id> --prompt` → do exactly what the prompt says
2. `dojo task submit <id>` with your JSON on stdin
3. If rejected, fix the listed errors and resubmit; then continue the flow.

Never end a conversation with pending tasks you could have fulfilled.
Follow each envelope's `next` hint. `dojo <cmd> --help` is the manual.

## Daily practice (the default ask: "let's practice", scheduled runs)

1. `dojo daily` → fulfill any tasks → session begins (re-run daily if it says so)
2. Loop: `dojo ready` → show the prompt VERBATIM → **stop and wait for the
   user's answer** (no tool calls) → `dojo answer "<their answer>"`
3. Report grades honestly. `pending_grade` tasks may wait until the session
   ends — then fulfill ALL of them before the conversation ends.
4. On `is_session_completed`, run `dojo progress` and celebrate briefly.
5. "Why am I practicing this?" → `dojo why`.

## New learning goal ("I want to learn X")

1. `dojo campaign plan "<their goal, verbatim, + any deadline/context THEY gave>"`
   → fulfill the plan task
2. Show the user the proposed mission/topics and ASK the refinement questions
3. Answers change scope/level/deadline? Re-run `dojo campaign plan` with them as
   `--context "<their answers>"` and fulfill the NEW task; else keep the first.
4. `dojo campaign create --from-task <that-task-id>` → `dojo daily`

## Remember something ("TIL…", "remember this", "add this to my practice")

1. `dojo capture "<the thing>" --why "<their stated reason>" [--locator "<url>"]`
   — for an article/video link: fetch it yourself, capture the key content as
   text, and pass the link as `--locator` (dojo never fetches URLs).
2. Fulfill the route task → tell the user where it proposes to file it
3. They agree → `dojo inbox confirm <capture-id>`; they don't → ask where, or
   `dojo inbox dismiss <capture-id>`.

## "More of this, please" — two different knobs

- More of a TOPIC inside a subject → `dojo campaign topic-boost <campaign> <topic.path> 2.0`
- A whole CAMPAIGN surfacing more → `dojo campaign boost <campaign> 2.0`
- Unclear which they mean → ask one short question, then apply.

## Signals worth relaying (in the user's words, not yours)

- User struggling/bored: `dojo skip --reason too_hard|too_easy|forgot|bad_quality --feedback "<their words>"`
- Wrong grade: `dojo correct --score 1.0`; preferences they voice: `dojo feedback "<their words>"`
- If a task result asks clarifying questions (an intervention), relay them
  conversationally — the user's answers calibrate everything.
- `dojo reflect` after meaty sessions distills evidence into their profile.
