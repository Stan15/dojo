# Sprint Plan: AI Command Connector End-to-End Slice

Status: sprint candidate
Audience: product/engineering
Goal: ship the smallest end-to-end AI connector path that lets a standalone Dojo app connect a command-backed AI, generate candidate practice from a source/goal, review/queue it, run a practice session, record an answer, and manually verify the loop.

## Product outcome

By the end of the sprint, a developer/user can run a full local workflow:

```bash
dojo init
dojo connect ai command hermes --default -- hermes chat -Q --stdin
dojo connect ai test hermes
dojo add --text "The product rule says d(uv)/dx = u'v + uv'." --title "Product rule" --topic math.calculus --generate
dojo source candidates <source-id>
dojo queue --source <source-id> --limit 1
dojo start
dojo answer "u'v + uv'"
dojo progress --recent 1
```

This does not need every future connector feature. It must prove that the standalone core can call an external AI command, store resulting artifacts, and use them in a real practice loop.

## Scope discipline

### Current sprint

- Generic command connector only.
- `connect ai` language stays as the public API.
- One default AI command for all AI tasks.
- Prompt-on-stdin as the default input mode.
- Parse JSON when available; otherwise preserve raw text and fail with useful diagnostics at validation gates.
- One or two task types only: candidate generation and optional JSON repair/test.
- Manual review/queue path is acceptable.
- Manual CLI testing is required.

### Explicit non-goals

- First-class OpenAI/Anthropic/Ollama/MCP connectors.
- Full provider matrix.
- Hosted backend.
- Web/mobile UI.
- Fully automatic source research.
- Advanced role routing.
- Perfect LLM output reliability.
- Polished TUI.

If command wrapping proves too painful for a specific integration, document the failure and decide whether that class needs a hand-coded adapter later. Do not pre-emptively build provider-specific implementations this sprint.

## Critical API surface for this sprint

Keep the syntax under `dojo connect ai`, not `dojo ai`.

### Connector setup

```bash
dojo connect ai command <name> --default -- <command...>
dojo connect ai command <name> \
  --input stdin-prompt|stdin-json|request-json-file \
  --output stdout-json|stdout-json-or-text|stdout-text \
  --timeout 120 \
  [--default] \
  -- <command...>
```

Acceptance criteria:

- Saves a connector descriptor in local config/state.
- Stores command as argv, not as shell string.
- Everything after `--` belongs to the external command.
- `--default` sets the global default connector.
- Fails clearly if no command is provided.

### Connector inspection and defaulting

```bash
dojo connect ai list
dojo connect ai show <name>
dojo connect ai use <name>
dojo connect ai remove <name>
```

Acceptance criteria:

- `list` shows connector name, kind, default marker, input/output modes, and last test status.
- `show` prints safe config and hides secrets/env values if any are added later.
- `use` changes the default connector.
- `remove` refuses to remove the default unless `--force` or a replacement default is provided.

### Connector test

```bash
dojo connect ai test [name] [--json]
```

Acceptance criteria:

- Runs a tiny deterministic smoke prompt through the command.
- Verifies command executable is found.
- Captures exit code, stdout, stderr tail, duration, and parse status.
- Stores last test result.
- Returns non-zero on command failure or timeout.

### AI task dry-run/debug

```bash
dojo connect ai request <task> --dry-run --json
```

Acceptance criteria:

- Prints the TaskRequest envelope and/or rendered prompt without invoking the connector.
- Supports at least `exercise.generate`.
- Lets us debug prompts before spending LLM calls.

### Minimal task override, if time permits

```bash
dojo connect ai task set <task> --connector <name> [--timeout N] [-- <command...>]
dojo connect ai task list
dojo connect ai task show <task>
dojo connect ai task clear <task>
```

Acceptance criteria:

- Not required for first E2E if global default works.
- Implement only after the global path is green.
- Must not block the source-to-practice loop.

## Implementation tasks

### Task 1: Preserve `connect ai` syntax in docs and CLI help

Objective: align the design docs and sprint implementation target with the preferred public language.

Files:

- Modify: `docs/ai-connector-interface.md`
- Modify if present: CLI help/command registration files under the Dojo package

Steps:

1. Ensure examples use `dojo connect ai command`, not `dojo ai add`.
2. Keep the distinction: minimal critical APIs vs reduced syntax.
3. Commit docs before code changes.

Verification:

```bash
grep -R "dojo ai add\|dojo ai task\|dojo ai list" docs/ || true
grep -R "dojo connect ai command" docs/
```

Expected: no old `dojo ai ...` examples remain except intentional migration notes.

### Task 2: Add connector config/state model

Objective: represent command connectors in local state without invoking them yet.

Files:

- Create/modify: core config module for standalone Dojo
- Create/modify: tests for connector config persistence

Model shape:

```yaml
ai:
  default_connector: hermes
  connectors:
    hermes:
      kind: command
      command: ["hermes", "chat", "-Q", "--stdin"]
      input_mode: stdin_prompt
      output_mode: stdout_json_or_text
      timeout_seconds: 120
      policy:
        allow_source_text: false
        allow_raw_answers: false
```

Tests:

- add connector saves argv and metadata;
- default connector is persisted;
- duplicate connector names require explicit replace;
- invalid names and empty commands fail.

Verification:

```bash
pytest tests -q -k "connector or ai"
```

### Task 3: Implement `dojo connect ai command`

Objective: let a user add a command connector from the CLI.

Behavior:

```bash
dojo connect ai command hermes --default -- hermes chat -Q --stdin
```

Acceptance criteria:

- Parses command args after `--` exactly as argv.
- Defaults to `input_mode=stdin_prompt`, `output_mode=stdout_json_or_text`, `timeout_seconds=120`.
- Writes state/config atomically.
- Prints next step: `dojo connect ai test hermes`.

Manual verification:

```bash
dojo connect ai command hermes --default -- python -c 'import sys; print(sys.stdin.read())'
dojo connect ai list
dojo connect ai show hermes
```

### Task 4: Implement connector invocation service

Objective: provide a library function that calls a command connector with a TaskRequest.

Core behavior:

- Resolve connector by explicit name or global default.
- Render TaskRequest into a clear prompt for `stdin_prompt`.
- Write JSON/temp files for `request_json_file` when configured.
- Run command with timeout.
- Capture stdout/stderr/exit code/duration.
- Parse JSON result if possible; otherwise return text artifact plus parse warning.

Tests:

- stdin prompt reaches subprocess;
- timeout is enforced;
- non-zero exit becomes structured failure;
- JSON stdout parses;
- text stdout is preserved.

Verification:

```bash
pytest tests -q -k "command_connector or invocation"
```

### Task 5: Implement `dojo connect ai test`

Objective: provide a fast smoke test and store the result.

Smoke prompt:

```text
Return the exact text: dojo-ai-connector-ok
```

Acceptance criteria:

- Runs against named or default connector.
- Shows status, duration, parse mode, and stderr tail if relevant.
- Stores last test result for `show/list`.
- Supports `--json`.

Manual verification:

```bash
dojo connect ai command echoer --default -- python -c 'import sys; print("dojo-ai-connector-ok")'
dojo connect ai test echoer
dojo connect ai show echoer
```

### Task 6: Add `exercise.generate` AI task contract

Objective: create the first real task that uses the connector.

Minimum TaskRequest fields:

```json
{
  "schema_version": "dojo.task_request.v1",
  "task": "exercise.generate",
  "intent": "Generate candidate practice items from this source/topic.",
  "context_blocks": [],
  "expected_artifacts": ["topic_span", "exercise_draft"],
  "output_schema": {}
}
```

Acceptance criteria:

- Prompt asks for a small JSON array of candidate drafts.
- Prompt tells the connector that a source may contain multiple subtopics; `--topic` is only a user hint/default parent topic.
- Prompt includes source title, source text when policy allows it, optional topic hint, and output constraints.
- Result validator accepts topic spans and at least one candidate with prompt, answer/rubric, topic path, source span reference, and difficulty/quality metadata.
- Invalid output is saved as a failed generation attempt with diagnostics, not silently discarded.

Tests:

- deterministic fake connector returns valid candidate JSON;
- fake connector can return candidates across two different subtopics for one source;
- malformed connector output yields validation error;
- source text is omitted when policy forbids it.

### Task 7: Wire AI generation into `dojo add` or source extraction

Objective: make the real product loop use the connector.

Preferred path:

```bash
dojo add notes.md --topic math.calculus --generate
```

Acceptable sprint path if `dojo add` is not ready:

```bash
dojo source add notes.md --topic math.calculus
dojo admin generate run --source <source-id> --connector hermes
```

Acceptance criteria:

- Source text becomes a TaskRequest.
- A single source may produce multiple topic spans and candidates across different subtopics.
- Connector result creates source candidates, not active exercises directly.
- Candidate records include provenance: source id/title, source span/offset or excerpt hash, inferred topic path, connector name, task id, prompt/schema version, raw output reference, validation status.
- CLI prints the next manual step: review/queue/start.

Manual verification:

```bash
printf 'The product rule says d(uv)/dx = u'"'"'v + uv'"'"'.' > /tmp/product-rule.txt
dojo add /tmp/product-rule.txt --topic math.calculus --generate
dojo source list
dojo source candidates <source-id>
```

### Task 8: Minimal review/queue bridge

Objective: get AI-generated candidates into a practice session with human control.

Acceptance criteria:

- User can list candidates for a source.
- User can queue/promote one candidate into an exercise.
- Promotion keeps source and AI provenance.
- Bad candidates can be rejected or ignored.

Manual verification:

```bash
dojo source candidates <source-id>
dojo queue --source <source-id> --limit 1
dojo start
```

### Task 9: End-to-end manual test script

Objective: make manual verification repeatable.

Create a documented script or checklist that runs the whole loop with a fake connector first, then Hermes if available.

Fake connector command:

```bash
python - <<'PY'
import json, sys
_ = sys.stdin.read()
print(json.dumps([
  {
    "prompt": "State the product rule for d(uv)/dx.",
    "answer": "u'v + uv'",
    "rubric": "Correct if both terms u'v and uv' are present.",
    "topic": "math.calculus",
    "difficulty": 0.35
  }
]))
PY
```

Acceptance criteria:

- Script/checklist starts from clean test state.
- Adds fake connector.
- Adds source.
- Generates candidate.
- Queues candidate.
- Starts session.
- Records answer.
- Shows progress or attempt record.

### Task 10: Smoke-test with a real command connector

Objective: manually test the same path with Hermes or another real command.

Command:

```bash
dojo connect ai command hermes --default -- hermes chat -Q --stdin
dojo connect ai test hermes
```

Acceptance criteria:

- At least one full source-to-practice run succeeds.
- Any LLM-output failure is diagnosable from saved raw output and validation errors.
- Observed friction is recorded as follow-up tasks, not solved by expanding sprint scope midstream.

## Suggested sprint order

1. Docs/API alignment: keep `connect ai` syntax.
2. Connector config model.
3. `connect ai command/list/show/use/remove`.
4. Command invocation service.
5. `connect ai test`.
6. `exercise.generate` TaskRequest + validator.
7. Wire into `dojo add`/source generation.
8. Review/queue bridge.
9. Fake connector E2E test.
10. Real Hermes E2E test.

## Definition of done

- Fresh local state can complete one source-to-practice loop with a fake connector.
- Fresh local state can attempt the same loop with Hermes via `dojo connect ai command hermes --default -- hermes chat -Q --stdin`.
- Connector failures are visible and actionable.
- Generated items remain candidates until queued/promoted.
- At least one manual test transcript/checklist is committed.
- Follow-up backlog captures provider-specific pain points before we decide to hand-code adapters.

## Backlog after sprint

- Task-specific connector invocations.
- Presets for Hermes/Claude/Codex.
- JSON repair task.
- Better schema-guided generation and retries.
- Provider-specific adapters only when command wrappers repeatedly fail.
- Capability declarations and policy UI.
- Token/cost reporting where available.
- Telegram adapter calls into the same standalone CLI/library path.
