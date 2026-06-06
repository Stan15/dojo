# Terminal UX and Tech Stack Recommendation

Status: design baseline
Audience: product/engineering/design
Purpose: choose the implementation stack and interaction patterns for a polished local-first terminal experience.

## Recommendation

Use Python for the first productionized Dojo core, with:

- `Typer` for the normal command surface;
- `Rich` for polished command output, prompts, panels, tables, trees, progress, and Markdown;
- `Textual` for the full interactive terminal app/TUI;
- SQLite for local-first storage;
- Pydantic for typed config/request/response objects;
- pytest for tests;
- uv for packaging and development workflow.

```text
Python core library
  -> Typer CLI
  -> Rich output/input helpers
  -> Textual TUI
  -> SQLite persistence
  -> optional providers/connectors/adapters
```

Keep product logic in the core services. The CLI and TUI should be clients over those services, not separate implementations.

## Why Python first

Dojo's early risk is not CPU performance. The risk is shipping a coherent source-to-practice learning loop without over-architecting. Python gives the best speed and ecosystem fit for:

- LLM/provider adapters;
- document/source extraction;
- scoring/verifier logic;
- SQLite-backed local state;
- structured data schemas;
- rapid iteration from the existing prototype;
- future sandboxed Python evaluators for verifiable grading.

Rust, Go, or TypeScript may be useful later for specific clients or helpers, but Python should own the first core.

## Terminal interface layers

Use two terminal layers:

### 1. Normal CLI

The normal CLI is for commands, scripts, docs, automation, and power users.

Examples:

```bash
dojo add notes.md --topic physics.relativity
dojo start
dojo answer "142"
dojo progress
dojo source review src_123
```

Stack:

```text
Typer + Rich
```

### 2. Full TUI

The full TUI is for immersive workflows:

```bash
dojo tui
# or later
dojo app
```

Stack:

```text
Textual
```

Use Textual for source review, practice sessions, progress drill-downs, provider setup, and dashboards.

## User input and choice selection

Input and choice selection should be designed as a shared interaction layer so commands and the TUI feel consistent.

### Principles

1. **Prefer safe defaults.**
   If a choice is obvious, select it and explain how to change it.

2. **Do not turn the CLI into a questionnaire.**
   Ask only for information required to proceed. Use `--guided` for richer onboarding flows.

3. **Every interactive command needs a non-interactive equivalent.**
   Scripts, adapters, tests, and agents must be able to pass flags or JSON instead of relying on prompts.

4. **Make destructive or privacy-sensitive choices explicit.**
   Examples: deleting data, sending source text to a remote model, enabling web research, exporting usage data.

5. **Use progressive disclosure.**
   Start with simple choices. Let power users drill into advanced controls.

6. **Support both keyboard-first and copy-paste-friendly operation.**
   Arrow keys and fuzzy search in TUI; numbered choices and flags in CLI.

## CLI input patterns

Use Rich/Typer for common command input.

### Confirmations

Use confirmations for destructive or privacy-sensitive actions:

```bash
dojo source remove src_123
# Remove source "Transformer notes" and 8 unqueued candidates? [y/N]
```

Non-interactive equivalent:

```bash
dojo source remove src_123 --yes
```

For dangerous actions, require explicit phrase or ID confirmation:

```bash
dojo reset --all-data
# Type "delete all local dojo data" to continue:
```

### Simple choices

Use numbered choices in the CLI:

```text
Choose a topic:
  1. math.linear_algebra
  2. math.calculus
  3. physics.relativity
  4. Create new topic

Selection [1]:
```

Non-interactive equivalent:

```bash
dojo add notes.md --topic math.linear_algebra
```

### Multi-select choices

Use checkbox-style numbered choices for reviewing candidates or selecting topics:

```text
Queue candidates:
  [1] Matrix-vector multiplication intuition
  [2] Eigenvector geometric meaning
  [3] Determinant as area scaling
  [4] Row reduction procedure

Select items, ranges, or all [1-3, all, none]:
```

Accepted input forms:

```text
1,3
1-3
all
none
```

Non-interactive equivalent:

```bash
dojo queue --candidate cand_1 --candidate cand_3
```

### Free text input

For short answers:

```bash
dojo answer
# Answer: _
```

But prefer direct argument support:

```bash
dojo answer "dx=-2 dy=1 facing=north"
```

For long answers or edits:

```bash
dojo answer --editor
```

This should open `$EDITOR`, then record the result.

### Guided flows

Use guided flows for onboarding and complex setup:

```bash
dojo init --guided
dojo connect provider setup --guided
dojo campaign create "Improve memory" --guided
dojo add notes.md --guided
```

Guided flows should be resumable or safely cancellable.

### Command palette-like CLI helper

A lightweight CLI launcher can help users discover actions without entering the full TUI:

```bash
dojo choose
```

Possible behavior:

```text
What do you want to do?
  1. Start practice
  2. Add source
  3. Review source candidates
  4. Show progress
  5. Configure providers
```

This is optional, but useful for users who do not remember commands.

## TUI input patterns

Use Textual for rich interaction.

### Global navigation

Suggested keys:

```text
?        help
Ctrl+K   command palette
q        back/quit current screen
/        search/filter
Enter    activate/select
Space    toggle selection
Tab      next focus
Shift+Tab previous focus
Esc      cancel/back
```

### Command palette

The TUI should have a command palette:

```text
Start practice
Add source
Review candidates
Show weak topics
Configure providers
Export Anki deck
```

This keeps the app discoverable without bloating top-level navigation.

### Source review UI

Source review should be a first-class TUI screen:

```text
Left: source outline / excerpts
Middle: candidate exercise cards
Right: details, answer/rubric, provenance, quality warnings
Bottom: Accept / Edit / Reject / Queue
```

Interactions:

- arrow keys move between candidates;
- `Space` toggles selection;
- `e` edits candidate;
- `a` accepts;
- `r` rejects;
- `q` queues accepted/selected;
- `/` filters by topic/type.

### Practice UI

Practice screen:

```text
Prompt card
Source/provenance hint
Timer / hint count / difficulty
Answer input
Actions: submit, hint, skip, correct, reveal explanation after grading
```

Important: timing should start when the prompt is revealed, not when the session summary opens.

### Provider setup UI

Provider setup should expose capabilities clearly:

```text
Provider: Hermes
Status: available
Roles: writer, planner, researcher
Capabilities:
  web: yes
  code execution: via harness / policy-gated
  structured output: prompt-only
  prompt caching: unknown
  local-only: no
```

The user should be able to test the provider from this screen.

## Shared interaction abstraction

Avoid hard-coding prompts all over the CLI. Build a small interaction service that can be backed by CLI, TUI, tests, or adapters.

Conceptual interface:

```python
class InteractionPort(Protocol):
    def confirm(self, message: str, *, default: bool = False, danger: bool = False) -> bool: ...
    def choose_one(self, message: str, choices: list[Choice], *, default: str | None = None) -> str: ...
    def choose_many(self, message: str, choices: list[Choice]) -> list[str]: ...
    def input_text(self, message: str, *, multiline: bool = False, default: str | None = None) -> str: ...
    def show(self, renderable: Renderable) -> None: ...
```

Implementations:

```text
CliInteractionPort      Rich/Typer prompts
TuiInteractionPort      Textual widgets/screens
JsonInteractionPort     non-interactive adapter/test mode
NoopInteractionPort     fails if input is required
```

This lets the same source-review or setup workflow run in different surfaces.

## Non-interactive mode

Every command should be able to run without prompts:

```bash
dojo add notes.md --topic math.linear_algebra --queue 3 --yes
dojo source remove src_123 --yes
dojo connect provider setup openai --api-key env:OPENAI_API_KEY --model gpt-4.1
dojo start --json
```

If required input is missing in non-interactive mode, fail with a structured error:

```json
{
  "ok": false,
  "error": {
    "code": "input_required",
    "message": "Topic selection is required.",
    "choices": ["math.linear_algebra", "math.calculus"],
    "next_actions": ["Pass --topic TOPIC or run with --guided."]
  }
}
```

## TTY detection

Dojo should detect whether it is running interactively.

```text
TTY present       -> prompts allowed unless --no-input
No TTY / --json   -> prompts disabled
--no-input        -> prompts disabled
--guided          -> prompts encouraged
```

Suggested flags:

```bash
--yes       assume yes for safe confirmations; still require explicit dangerous confirmations
--no-input  never prompt
--json      machine output; implies no interactive prompts unless explicitly allowed
--guided    ask helpful questions
--editor    open editor for multiline text
```

## Validation and cancellation

All prompts should support:

- validation messages;
- cancel/back;
- defaults;
- retry;
- clear error states.

If the user cancels, no partial state should be committed unless the command says it saved a draft.

For multi-step guided flows, save drafts only when useful and say where:

```text
Campaign draft saved. Resume with:
  dojo campaign resume draft_123
```

## What not to do

Do not require users to type command-only control words inside the TUI when buttons/keys are available.

Do not make Telegram/Hermes-specific reply conventions part of the core UX.

Do not prompt for fields that can be inferred safely.

Do not hide important privacy choices behind defaults.

Do not rely on interactive prompts for adapter/script flows.

## MVP recommendation

Implement in this order:

1. Core service methods accept explicit arguments and return typed results.
2. Typer commands wrap those methods.
3. Rich renderers display results.
4. A small `InteractionPort` supports `confirm`, `choose_one`, `choose_many`, and `input_text`.
5. Add guided CLI flows for `init`, `add`, provider setup, and source review.
6. Add Textual TUI only after the CLI/service loop is stable.

This keeps the product usable immediately while preserving a path to a beautiful terminal app.
