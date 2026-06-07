# AI Connector Interface

Status: design baseline
Audience: product/engineering
Purpose: define a connector interface for arbitrary LLMs, local endpoints, subscriptions, agent harnesses, and custom commands that is aware of web/code/tooling needs without assuming Dojo controls the model.

## Core insight

Dojo cannot assume that a connected LLM can call tools, follow one API shape, stream tokens, use JSON mode, browse the web, execute code, or report cost. It may be:

- a raw hosted API;
- a local OpenAI-compatible endpoint;
- a paid AI subscription wrapped by a CLI;
- an agent harness such as Hermes, Claude Code, Codex, or OpenCode;
- a custom user command;
- a future MCP/server/tool bridge;
- a no-LLM deterministic fallback.

Therefore the connector interface must separate:

```text
What Dojo needs done
  from
How the connected intelligence can do it
  from
What evidence/provenance Dojo requires before trusting the result
```

The LLM/harness can propose exercises, rubrics, verifiers, tests, sources, hints, grades, or learner insights. Dojo decides whether the proposal is valid enough to store, queue, run, grade, or schedule.

## Design stance

Build the connector interface around **typed tasks**, **declared capabilities**, **tool grants**, **artifacts**, and **validation gates**.

```text
Dojo TaskRequest
  -> Connector capability/policy check
  -> Connector invocation
  -> ConnectorResult with artifacts/provenance
  -> Dojo validation/repair/approval
  -> Durable Dojo state
```

The connector is not the source of truth. The connector is a worker that returns evidence-bearing artifacts.

## User-facing connection model

MVP scope: **command connectors only**. Hosted APIs, OpenAI-compatible endpoints, Ollama, MCP, and direct SDK integrations can all be wrapped by commands for now. Dojo should not create first-class provider integrations until real usage proves that command wrapping is too painful for a specific class.

The minimal command family is:

```bash
dojo connect ai command <name> -- <command...>
dojo connect ai use <name>
dojo connect ai test [name]
dojo connect ai list
dojo connect ai show <name>
dojo connect ai remove <name>
```

### Minimal quick path

A user should be able to configure one AI command for every AI-assisted task with one command:

```bash
dojo connect ai command hermes --default -- hermes chat -Q --stdin
```

That writes one connector and makes it the global default. Dojo builds a typed TaskRequest internally, renders it into a plain-text prompt by default, sends that prompt to the command on stdin, then accepts useful text or parseable JSON on stdout. Commands that want the raw JSON envelope can opt into `stdin-json` or `request-json-file`.

Equivalent explicit form:

```bash
dojo connect ai command hermes \
  --default \
  --input stdin-prompt \
  --output stdout-json-or-text \
  --timeout 120 \
  -- hermes chat -Q --stdin
```

### Command separator rule

Everything after `--` is the external command and its arguments. This avoids shell-quoting ambiguity and keeps the Dojo CLI small:

```bash
dojo connect ai command codex --default -- codex exec
dojo connect ai command claude --default -- claude -p
dojo connect ai command custom --default -- /usr/local/bin/my-llm --input -
```

If users need shell features such as pipes, redirection, aliases, or environment setup, they should create a wrapper script and point Dojo at it:

```bash
dojo connect ai command my-wrapper --default -- ~/.local/bin/dojo-ai-wrapper
```

### Built-in command presets are optional sugar

Dojo may provide a few presets, but they should compile down to the same command descriptor rather than becoming separate connector implementations:

```bash
dojo connect ai preset hermes --default
# expands to roughly: dojo connect ai command hermes --default -- hermes chat -Q --stdin

dojo connect ai preset claude --default
# expands to roughly: dojo connect ai command claude --default -- claude -p

dojo connect ai preset codex --default
# expands to roughly: dojo connect ai command codex --default -- codex exec
```

Known presets may hide provider-specific housekeeping flags. For example, Hermes supports `--source TAG`, but that is a session/source tag for Hermes bookkeeping, not the system prompt. Dojo may add `--source dojo` internally for a Hermes preset, but the user-facing command should not require users to know or pass it.

This is not the same as hand-coding each provider's full behavior. The MVP should have **one generic command adapter** plus small preset definitions that only provide default command arguments, input/output defaults, and test prompts.

### Custom command with request-file input

Some commands do not read stdin well. The minimal surface supports a request file placeholder:

```bash
dojo connect ai command my-llm \
  --input request-json-file \
  --output stdout-json \
  -- /usr/local/bin/my-llm --input {request_json}
```

Placeholders allowed in command args:

```text
{request_json}   path to the full TaskRequest JSON file
{prompt_txt}     path to a rendered plain-text prompt file
{output_json}    path where the command should write ConnectorResult JSON, if using file output
```

### Minimal management commands

```bash
# List configured commands and defaults.
dojo connect ai list

# Inspect saved command, policy, capabilities, and last test result.
dojo connect ai show hermes

# Set the global default connector.
dojo connect ai use hermes

# Remove a connector.
dojo connect ai remove hermes

# Run smoke tests against the connector.
dojo connect ai test hermes

# Print the exact request Dojo would send for a task without invoking AI.
dojo connect ai request exercise.generate --dry-run --json
```

### Role assignment and per-task commands

The MVP does not need many user-facing roles. Start with one default connector, then allow optional task-specific overrides only when users need them.

```bash
# One default connector for all AI tasks.
dojo connect ai command hermes --default -- hermes chat -Q --stdin

# Optional: set an existing connector as the default for one task family.
dojo connect ai task set answer.grade_freeform --connector hermes

# Optional: override the actual command for one task family.
dojo connect ai task set answer.grade_freeform \
  --connector hermes \
  --timeout 45 \
  -- hermes chat -Q --max-turns 2 --stdin

# Optional: list or clear overrides.
dojo connect ai task list
dojo connect ai task show answer.grade_freeform
dojo connect ai task clear answer.grade_freeform
```

Task overrides are invocation profiles under the same connector. This avoids creating fake separate providers such as `hermes_grader`, `hermes_researcher`, and `hermes_repair` unless the user wants that.

Keep role aliases as a later convenience, not as MVP surface. If added, they should map to task groups internally:

```bash
dojo connect ai role set grader hermes     # optional future sugar for answer.* tasks
dojo connect ai role set writer hermes     # optional future sugar for exercise.* tasks
dojo connect ai role list
```

Suggested config shape:

```yaml
ai:
  connectors:
    hermes:
      kind: command_harness
      default_invocation:
        command: hermes
        args: ["chat", "-Q", "--stdin"]
        output_mode: stdout_json_extract
      task_invocations:
        answer.grade_freeform:
          args: ["chat", "-Q", "--max-turns", "2", "--stdin"]
          timeout_seconds: 45
          capabilities_override:
            web: {supported: false}
            code_execution: {supported: false}
        exercise.generate_researched:
          args: ["chat", "-Q", "--max-turns", "10", "--stdin"]
          timeout_seconds: 240
          capabilities_override:
            web: {supported: true, owner: harness}
            code_execution: {supported: true, owner: harness}
        json.repair:
          args: ["chat", "-Q", "--max-turns", "1", "--stdin"]
          timeout_seconds: 30
```

Resolution order:

```text
explicit per-call connector flag
  -> task-specific invocation override
  -> global default command connector
  -> deterministic fallback / safe failure
```

User-facing language should distinguish:

```text
connector = the AI system/account/harness, e.g. Hermes or local OpenAI endpoint
invocation = how Dojo calls that connector for this task
role = which connector/invocation is preferred for a class of tasks
```

### Capability testing

Connection should include tests that produce a capability report.

```bash
dojo connect ai test hermes
```

Test categories:

```text
basic_chat           can produce a response
structured_output    can return or be parsed into JSON
schema_following     can satisfy a small schema
latency              approximate response time
usage_reporting      token/cost metadata available or unknown
web                  can cite a fetched/search result, if declared
code                 can solve or run a tiny verifier, if declared
privacy              local-only or remote/unknown
```

Dojo should store results as observations, not absolute truth. Harness capabilities can change with user config.

Example report:

```text
Connector: hermes
Kind: command_harness
Status: available

Capabilities:
  chat: yes
  structured output: prompt-only, parseable in test
  web: declared harness-owned, citation test passed
  code execution: declared harness-owned, sandbox unknown
  prompt cache: unknown
  usage/cost reporting: unknown
  local-only: no

Recommended roles:
  writer: yes
  researcher: yes
  planner: yes
  live grader: no, unless latency is acceptable
```

### Privacy and cost prompts

For remote or opaque connectors, setup should ask a small number of high-value questions:

```text
May Dojo send source excerpts to this connector? [y/N]
May Dojo send raw answers for grading? [y/N]
Daily budget for this connector? [$0.50]
Use this connector for live grading? [y/N]
```

Equivalent config should be editable:

```bash
dojo connect ai policy set hermes --allow-source-text false
dojo connect ai policy set hermes --allow-raw-answers true --daily-budget 1.00
dojo connect ai policy show hermes
```

### Generated config shape

The command-only MVP should write a config like:

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
      capabilities:
        chat: true
        structured_output:
          mode: prompt_only
        usage_reporting: unknown
      policy:
        allow_source_text: false
        allow_raw_answers: false
        max_cost_usd_per_day: null
      task_invocations:
        answer.grade_freeform:
          command: ["hermes", "chat", "-Q", "--max-turns", "2", "--stdin"]
          timeout_seconds: 45
```

### Non-interactive setup

Everything the guided flow does should have a non-interactive form:

```bash
dojo connect ai command hermes \
  --default \
  --input stdin-prompt \
  --output stdout-json-or-text \
  --timeout 120 \
  --no-source-text \
  --test \
  -- hermes chat -Q --stdin
```

In `--json` or `--no-input` mode, missing required settings should fail with structured guidance rather than prompting.

### User mental model

For the user, setup should feel like:

```text
1. Choose what AI system you already use.
2. Tell Dojo how to call it.
3. Dojo tests what it can do.
4. Pick what jobs it should handle.
5. Set privacy/cost boundaries.
```

The internal connector model remains rich, but the onboarding flow stays small.

## Connector types

### Raw chat/API connector

Examples: OpenAI, Anthropic, Gemini, OpenRouter, local OpenAI-compatible server, Ollama-compatible wrapper.

Characteristics:

- Dojo owns most web/code/tool work;
- model receives bounded context;
- may support JSON schema/function calling;
- usage/cost may be available;
- good for extraction, generation, grading, hints, summaries.

### Command connector

Examples:

```bash
hermes chat ...
claude -p ...
codex exec ...
opencode run ...
my-llm-wrapper --input request.json
```

Characteristics:

- can wrap subscriptions or harnesses;
- may have tools unknown to Dojo;
- output format may be messy;
- cost may be opaque;
- best with request files and stdout JSON.

### Harness connector

Examples: Hermes, Claude Code, Codex, OpenCode.

Characteristics:

- can use skills, tools, files, shell, web, memory, plans;
- useful for research-heavy generation and campaign design;
- weaker reproducibility unless constrained;
- must return structured artifacts and citations.

### Deterministic connector

Examples: heuristic extraction, deterministic generator, local scorer, verifier-only path.

Characteristics:

- no LLM required;
- highly reproducible;
- important fallback and baseline.

## Connector capability descriptor

A connector should declare capabilities with uncertainty allowed. Unknown is better than pretending.

```yaml
connectors:
  hermes:
    kind: command
    command: ["hermes", "chat", "-Q", "--stdin"]
    input_mode: stdin_prompt
    output_mode: stdout_json_or_text
    timeout_seconds: 120
    capabilities:
      chat: true
      structured_output:
        mode: prompt_only
        schemas: false
      prompt_cache:
        supported: unknown
      web:
        supported: unknown
        owner: command
      code_execution:
        supported: unknown
        owner: command
      usage_reporting: unknown
    safety:
      local_only: false
      sends_data_remote: depends_on_command
      max_timeout_seconds: 180
```

## Task request envelope

Every connector call should be a typed request, not an unstructured chat blob.

```json
{
  "schema_version": "dojo.task_request.v1",
  "request_id": "taskreq_123",
  "task": "exercise.generate",
  "intent": "Generate 4 source-grounded practice candidates about matrix multiplication.",
  "privacy_level": "source_text_allowed",
  "tool_policy": {
    "strategy": "dojo_first_then_harness",
    "allowed_tool_owners": ["dojo", "harness"],
    "allow_web": true,
    "allow_code_execution": true,
    "require_citations_if_web_used": true,
    "require_verifier_if_code_used": true,
    "max_cost_usd": 0.25,
    "timeout_seconds": 180
  },
  "capability_requirements": {
    "structured_output": true,
    "citations": true
  },
  "context_blocks": [],
  "expected_artifacts": [
    "exercise_drafts",
    "citations",
    "verifier_specs"
  ],
  "output_schema": {}
}
```

## Connector result envelope

A connector result is not just text. It is an artifact bundle plus provenance.

```json
{
  "schema_version": "dojo.connector_result.v1",
  "request_id": "taskreq_123",
  "connector": "hermes",
  "ok": true,
  "artifacts": [
    {
      "type": "exercise_draft",
      "id": "draft_1",
      "content": {}
    },
    {
      "type": "verifier_spec",
      "id": "verifier_1",
      "content": {}
    },
    {
      "type": "citation_set",
      "id": "cites_1",
      "content": {}
    }
  ],
  "provenance": {
    "model": "unknown/configured-by-harness",
    "connector_kind": "command_harness",
    "tool_owner": "harness",
    "prompt_hash": "...",
    "schema_hash": "...",
    "adapter_version": "command.v1"
  },
  "usage": {
    "input_tokens": null,
    "output_tokens": null,
    "cache_read_tokens": null,
    "cache_write_tokens": null,
    "estimated_cost_usd": null
  },
  "warnings": []
}
```

## Artifact types

The connector interface should support multiple artifact types because LLM-backed work is often multi-part.

Important artifacts:

```text
source_extract
  Concepts, claims, snippets, citations, defer/noise notes.

exercise_draft
  Prompt, answer/rubric, target skill, difficulty, source links.

rubric_spec
  Grading dimensions, correct/partial/incorrect anchors, examples.

verifier_spec
  A proposed deterministic or sandboxed verifier for this exercise family/item.

verifier_code
  Optional proposed code implementing a verifier. Never trusted directly.

test_case_set
  Tests for verifier/spec validation: inputs, expected outputs, edge cases.

citation_set
  URLs/source ids/snippet ids used by a draft.

grade_result
  Score, dimensions, confidence, evidence, error tags.

hint_result
  Hint text plus leak-risk metadata.

learner_insight_proposal
  Hypothesis/evidence/scaffold proposal, not direct learner-state mutation.
```

## Verifiers are learned/generated artifacts

The important correction: many verifiers cannot be prebuilt because the user may ask to learn arbitrary things. The LLM/harness may need to design the verifier or grader for the task.

So Dojo should treat verifiers as **artifacts to be proposed, validated, versioned, and sandboxed**, not as a fixed library.

```text
User goal/source/topic
  -> connector proposes exercise draft + rubric + verifier spec
  -> Dojo validates the verifier spec structurally
  -> optional sandbox compiles/runs verifier code on generated tests
  -> Dojo stores verifier as experimental/reviewed/trusted
  -> attempts are graded with that verifier version
```

### Verifier lifecycle

```text
proposed
  Connector produced verifier spec/code/test cases.

validated
  Schema valid, sandbox safe enough to run, tests pass, no obvious leakage.

experimental
  Can be used for candidate review or low-stakes grading with confidence caveat.

reviewed
  Human or stronger audit approved it for normal scheduling.

trusted
  Stable built-in or heavily tested verifier family.

retired
  Superseded or found flawed. Attempts can be regraded with newer version.
```

### Verifier spec shape

Prefer declarative verifier specs before arbitrary code.

```json
{
  "type": "verifier_spec",
  "schema_version": "dojo.verifier_spec.v1",
  "verifier_kind": "numeric_equivalence | symbolic | rubric | regex | test_cases | python_sandbox | external_command",
  "scope": {
    "exercise_family": "grid_path_shortest",
    "exercise_id": "optional_specific_exercise"
  },
  "input_contract": {
    "answer_format": "compact path directions such as N1 E3",
    "normalization": ["uppercase", "expand run lengths", "ignore extra spaces"]
  },
  "grading_contract": {
    "score_range": [0, 1],
    "correct_if": ["path reaches goal", "path avoids blocked cells", "path length is minimal"],
    "partial_credit": []
  },
  "test_cases": [
    {
      "input": "N1 E3 N1",
      "expected": {"correct": true}
    }
  ],
  "safety": {
    "requires_code_execution": false,
    "network_required": false,
    "filesystem_required": false
  }
}
```

### Verifier code policy

If the connector returns code, Dojo should treat it as untrusted.

Rules:

- run only in a sandbox;
- network off by default;
- temp filesystem only;
- CPU/time/memory limits;
- no access to Dojo config, DB, secrets, home directory, SSH keys, browser profile, or provider credentials;
- require test cases;
- store code hash and verifier version;
- expose confidence/status in grading results;
- allow regrading when verifier changes.

For MVP, support only a narrow sandbox, probably Python, and only after deterministic spec validation.

## Task-scoped tool grants

Tool access should be granted per task request, not per connector globally.

```json
{
  "tool_grants": [
    {
      "tool": "web.fetch",
      "owner": "dojo",
      "scope": ["https://example.com/article"],
      "network": true,
      "requires_citation": true
    },
    {
      "tool": "code.run_python_sandbox",
      "owner": "dojo",
      "network": false,
      "filesystem": "temp_only",
      "timeout_seconds": 5
    },
    {
      "tool": "harness.tools",
      "owner": "harness",
      "allowed": true,
      "requires_evidence": ["citations", "tool_summary"]
    }
  ]
}
```

A raw local model may receive no tool grants, but still receive Dojo-owned tool outputs. A harness may receive permission to use its own tools, but must return evidence.

## Tool evidence requirements

If a connector or harness uses tools, it should return evidence in a normalized shape.

Web evidence:

```json
{
  "type": "web_evidence",
  "sources": [
    {
      "url": "https://example.com/article",
      "title": "...",
      "retrieved_at": "...",
      "snippet_ids": ["src_1#p3", "src_1#p4"]
    }
  ]
}
```

Code evidence:

```json
{
  "type": "code_evidence",
  "sandbox": "dojo-python-v1",
  "network": false,
  "timeout_seconds": 5,
  "code_hash": "...",
  "tests_run": 12,
  "tests_passed": 12,
  "stdout_excerpt": "",
  "stderr_excerpt": ""
}
```

If evidence is missing, the artifact can still be stored as a draft, but it should not be promoted to reviewed/trusted or used for high-confidence grading.

## Connector method surface

Conceptual Python interface:

```python
class AIConnector(Protocol):
    name: str
    descriptor: ConnectorDescriptor

    def health(self) -> ConnectorHealth:
        ...

    def dry_run(self, request: TaskRequest) -> CapabilityDecision:
        ...

    def run(self, request: TaskRequest) -> ConnectorResult:
        ...
```

Router:

```python
class AIRouter:
    def run_task(self, request: TaskRequest, *, connector: str | None = None) -> ValidatedResult:
        # 1. Resolve task -> role -> connector.
        # 2. Check privacy/cost/tool policy.
        # 3. Pre-run Dojo-owned tools if strategy says so.
        # 4. Invoke connector.
        # 5. Parse/repair/validate artifacts.
        # 6. Run local quality/verifier/safety gates.
        # 7. Return validated result or safe failure.
        ...
```

## Validation pipeline

Connector output should pass a layered validation pipeline.

```text
Parse
  -> extract JSON / artifacts from connector output

Schema validation
  -> artifact types and required fields

Policy validation
  -> privacy, cost, tool grants, citation requirements

Evidence validation
  -> sources exist, snippets are linked, tool summaries present

Safety validation
  -> no unsafe code execution, no secret access, sandbox constraints

Quality validation
  -> exercise usefulness, non-duplication, answer/rubric consistency

Promotion decision
  -> draft / experimental / reviewed / trusted / reject
```

This lets Dojo accept useful ideas from weak connectors without over-trusting them.

## Handling connectors with poor structured output

Command harnesses and subscriptions may not reliably emit pure JSON. The adapter should support:

1. request file input when possible;
2. clear sentinel markers around JSON;
3. extraction of the largest valid JSON block;
4. one repair attempt using a repair connector or local parser;
5. schema validation;
6. safe failure with captured raw-output hash.

Prompt pattern:

```text
Return exactly one JSON object between these markers:
<DOJO_JSON>
...
</DOJO_JSON>
No prose outside the markers.
```

The adapter still must tolerate prose outside the markers.

## Storage/audit model

Store enough to reproduce, audit, or regrade without storing unnecessary private raw text.

Suggested tables/records:

```text
ai_connector_runs
  id, task, connector, connector_kind, request_hash, prompt_hash,
  policy_json, started_at, completed_at, ok, error_code

ai_artifacts
  id, run_id, artifact_type, artifact_status, content_json_or_path,
  content_hash, schema_version, created_at

verifiers
  id, kind, status, scope_json, spec_json, code_hash,
  test_summary_json, sandbox_policy_json, created_by_run_id, version, created_at

verifier_runs
  id, verifier_id, attempt_id, sandbox_json, result_json,
  stdout_hash, stderr_hash, created_at
```

## MVP connector scope

Build the interface now, keep implementations narrow.

MVP connectors:

1. `builtin` deterministic/no-LLM connector for safe fallback paths.
2. `command` connector for Hermes/Claude/Codex/custom commands.

Defer first-class `openai_compatible`, hosted API, Ollama, MCP, and SDK connectors. They can be reached through command wrappers until real usage shows that a generic command adapter is not enough.

MVP artifacts:

1. `source_extract`
2. `exercise_draft`
3. `rubric_spec`
4. `verifier_spec`
5. `test_case_set`
6. `grade_result`
7. `citation_set`

MVP policies:

1. local-only mode;
2. no prompts in `--json`/`--no-input` mode;
3. require citations when web is used;
4. require sandbox when verifier code is used;
5. no live web grading by default;
6. promotion status: draft/experimental/reviewed/trusted/rejected.

## Recommended mental model

Dojo should not ask: “Can this LLM use tools?”

Dojo should ask:

```text
What task is this?
What artifacts do we need?
What capabilities are required?
Who is allowed to run tools?
What evidence must come back?
What validation gates must pass before we trust it?
```

That is the connector interface.
