---
name: dojo
description: "Daily learning practice engine. Use when the user wants to learn/study/practice/memorize a topic or skill, says 'quiz me' or 'train me', wants to remember something they just learned ('TIL', 'remember this'), or asks about their learning progress. Knowledge/learning contexts only, not physical workouts."
metadata:
  owner: github.com/Stan15/dojo
---

# Dojo

Local learning engine. Drive it with CLI commands; always pass `--json`.

## The one protocol that matters

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
3. Report the grade; if `pending_grade`, fulfill the grade task first, honestly.
4. On `is_session_completed`, run `dojo progress` and celebrate briefly.
5. "Why am I practicing this?" → `dojo why`.

## New learning goal ("I want to learn X")

1. `dojo campaign plan "<goal + any deadline/context>"` → fulfill the plan task
2. Show the user the proposed mission/topics and ASK the refinement questions
3. After they answer: `dojo campaign create --from-task <task-id>` → `dojo daily`

## Remember something ("TIL…", "remember this", "add this to my practice")

1. `dojo capture "<the thing>" --why "<their stated reason, if any>"`
2. Fulfill the route task → tell the user where it proposes to file it
3. They agree → `dojo inbox confirm <capture-id>`; they don't → ask where, or
   `dojo inbox dismiss <capture-id>`.

## "More of this, please" — two different knobs

- More of a TOPIC inside a subject → `dojo campaign topic-boost <campaign> <topic.path> 2.0`
- A whole CAMPAIGN surfacing more → `dojo campaign boost <campaign> 2.0`
- Unclear which they mean → ask one short question, then apply.

## Signals worth relaying

- User struggling/bored: `dojo skip --reason too_hard|too_easy|forgot|bad_quality --feedback "<their words>"`
- Wrong grade: `dojo correct --score 1.0`
- Any learning preference they voice: `dojo feedback "<their words>"`
- If a generation task's result asks clarifying questions (an intervention),
  relay them to the user conversationally — their answers calibrate everything.
- `dojo reflect` after meaty sessions distills evidence into their profile.
