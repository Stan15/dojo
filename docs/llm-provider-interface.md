# LLM Provider and Harness Interface Design

Status: design baseline
Audience: product/engineering
Purpose: define an LLM integration model that is provider-agnostic, harness-aware, cost-conscious, and compatible with local-first Dojo.

## Deeper problem

The feature is not merely “let the user choose OpenAI vs Anthropic.” Dojo needs an abstraction for **language-model work** that can be satisfied by many execution environments:

- hosted AI subscriptions and APIs;
- local OpenAI-compatible endpoints;
- local runtimes such as Ollama, llama.cpp, vLLM, LM Studio;
- full harnesses such as Hermes, Claude Code, Codex, OpenCode, or future agent runners;
- user-supplied shell commands;
- MCP servers or plugin systems;
- deterministic/no-LLM fallbacks.

The core product must not depend on any one harness, but it should be able to take advantage of a harness when present: tools, skills, prompt caching, memory, system prompt composition, structured-output repair, and multi-step research/generation.

## Main goal

Dojo should express **what it needs done** and let a configured provider/harness decide **how to do it**, within explicit capability, privacy, cost, and quality boundaries.

```text
Dojo task request
  -> LLM capability router
  -> provider/harness adapter
  -> normalized result + provenance + cost/usage metadata
  -> quality gate / deterministic validation
  -> Dojo state
```

Dojo owns the learning state. LLMs and agent harnesses are replaceable workers.

## Non-goals for MVP

Do not build a full agent framework inside Dojo.

Do not make a remote LLM mandatory for the core loop.

Do not let raw LLM outputs directly mutate durable learning state without validation.

Do not require users to copy their entire Hermes/Claude/Codex setup into Dojo. Integration should be by capability and command/provider config.

Do not assume every provider supports tools, system prompts, prompt caching, JSON mode, streaming, long context, image/audio, or persistent memory.

## Terminology

### Provider

A configured way to run an LLM call. Examples:

- `openai`
- `anthropic`
- `ollama`
- `openai-compatible-local`
- `hermes`
- `claude-code`
- `codex`
- `custom-command`

### Harness

A provider that is more than a raw model API. A harness may support tools, skills, memory, plans, subprocess work, file access, web access, prompt caching, retries, or agent loops.

Examples: Hermes, Claude Code, Codex CLI, OpenCode.

### LLM task

A typed Dojo operation that may need language-model intelligence. Examples:

- generate candidate exercises from a source;
- extract concepts from source text;
- grade a free-form answer with a rubric;
- summarize learner evidence into a profile hypothesis;
- propose topic consolidation;
- generate hints;
- repair malformed draft JSON;
- research a topic for campaign design.

### Adapter

A small implementation that turns Dojo's typed request into a provider/harness-specific call and returns normalized results.

## First-principles needs of LLM usage in Dojo

Dojo needs LLMs for different job classes, not one generic “chat” call.

### 1. Source extraction

Input:

- source text or chunk;
- source metadata;
- topic-interest profile;
- extraction policy;
- privacy/cost constraints.

Output:

- concepts;
- candidate exercise seeds;
- claim/provenance references;
- confidence;
- noise/defer notes.

Needs:

- structured output;
- chunking;
- provenance preservation;
- dedupe fingerprints;
- low hallucination tolerance;
- local deterministic fallback for simple text.

### 2. Exercise generation

Input:

- topic path;
- topic-interest profile;
- source candidates/provenance;
- learner profile summary;
- target skill/objective;
- difficulty band;
- desired item types;
- quality rubric.

Output:

- candidate drafts;
- answer/rubric;
- target skill;
- difficulty estimate;
- quality evidence;
- rationale.

Needs:

- structured output;
- high prompt quality;
- explicit quality evidence;
- bounded generation count;
- deterministic quality gate before queueing;
- no silent direct scheduling of unreviewed drafts unless policy allows.

### 3. Free-form scoring / rubric grading

Input:

- prompt;
- expected answer/rubric;
- raw answer;
- normalized answer;
- timing/hints/corrections/self-rating;
- scorer policy.

Output:

- correctness/score;
- dimensions;
- error tags;
- brief feedback;
- confidence;
- scorer metadata.

Needs:

- stable rubric versions;
- structured JSON;
- calibration examples;
- model/provider provenance;
- regrading support;
- low latency for session UX;
- deterministic scorer preferred when possible.

### 4. Hint generation

Input:

- current prompt;
- answer spec/rubric;
- hint level;
- prior hints;
- user answer if any;
- no-solution-leak policy.

Output:

- hint text;
- whether it risks revealing answer;
- metadata for hint count.

Needs:

- strict no-answer-leak constraints;
- low latency;
- ability to operate without broad context.

### 5. Learner insight distillation

Input:

- attempt history summaries;
- active hypotheses;
- error tags;
- user feedback;
- topic-interest profile.

Output:

- compact hypothesis update proposal;
- confidence;
- evidence links;
- suggested scaffolds;
- decay/reversal policy.

Needs:

- selective triggering, not every answer;
- compact context;
- durable provenance;
- human/admin auditability;
- no raw vulnerable chat text as primary generator input.

### 6. Topic/category consolidation

Input:

- topic tree;
- practice counts;
- source topics;
- user priorities;
- retention burden;
- candidate duplicate/overlap flags.

Output:

- proposed merges/splits/shelves/renames;
- questions for user;
- reversible action plan.

Needs:

- no direct DB surgery;
- proposed actions, not silent mutation;
- explanation simple enough for average users;
- advanced controls for power users.

### 7. Campaign planning/calibration

Input:

- vague user goal;
- existing topic/profile state;
- source material;
- constraints/cadence;
- optional research context.

Output:

- scope;
- calibration questions;
- diagnostic ladder;
- campaign plan;
- exercise templates;
- success indicators.

Needs:

- sometimes web/research/tools;
- may benefit from harness/agent rather than raw LLM;
- must avoid overbuilding a giant curriculum before calibration.

## Provider capability model

Each provider/harness declares capabilities. Dojo routes tasks based on requirements.

Example fields:

```yaml
providers:
  hermes:
    type: command
    command: hermes
    args: ["chat", "-Q", "--source", "dojo", "-q", "{prompt}"]
    capabilities:
      chat: true
      structured_output: prompt_only
      tools: true
      web: true
      file_context: true
      skills: true
      system_prompt: true
      prompt_cache: unknown
      streaming: false
      images: false
      max_context_tokens: unknown
      local_only: false
      cost_visibility: unknown
      can_run_agent_loop: true
    privacy:
      sends_source_text_remote: depends_on_harness
      allowed_data: [source_chunks, learner_summaries, prompts]
    reliability:
      timeout_seconds: 180
      retries: 1
```

Raw OpenAI-compatible local endpoint:

```yaml
providers:
  local_openai:
    type: openai_compatible
    base_url: http://localhost:11434/v1
    api_key: env:DOJO_LOCAL_OPENAI_API_KEY
    model: qwen2.5:14b
    capabilities:
      chat: true
      structured_output: json_schema
      tools: false
      web: false
      file_context: false
      skills: false
      system_prompt: true
      prompt_cache: false
      streaming: true
      images: false
      local_only: true
      can_run_agent_loop: false
    privacy:
      sends_source_text_remote: false
```

Hosted API:

```yaml
providers:
  anthropic:
    type: anthropic
    api_key: env:ANTHROPIC_API_KEY
    model: claude-sonnet-4
    capabilities:
      chat: true
      structured_output: tool_schema
      tools: false
      web: false
      file_context: false
      skills: false
      system_prompt: true
      prompt_cache: true
      streaming: true
      images: true
      local_only: false
      cost_visibility: estimated
```

Custom command:

```yaml
providers:
  my_command:
    type: command
    command: /usr/local/bin/my-llm-wrapper
    args: ["--task", "{task}", "--input", "{input_json_path}"]
    input_mode: file_json
    output_mode: stdout_json
    capabilities:
      chat: true
      structured_output: native_json
      tools: false
      system_prompt: true
```

## Task routing model

Dojo should not expose a single global “model” flag as the only control. It should support task-specific routing.

```yaml
llm:
  default_provider: local_openai
  tasks:
    source.extract:
      provider: local_openai
      fallback: heuristic
    exercise.generate:
      provider: hermes
      fallback: none
    answer.grade_freeform:
      provider: anthropic
      fallback: manual_self_grade
    hint.generate:
      provider: local_openai
      fallback: static_hint
    learner.distill:
      provider: local_openai
      fallback: deterministic_tags_only
    topic.consolidate:
      provider: hermes
      fallback: deterministic_report
    campaign.plan:
      provider: hermes
      fallback: guided_questions_only
```

CLI overrides:

```bash
dojo add notes.md --provider local_openai
dojo admin generate run --provider hermes
dojo answer "..." --grader anthropic
dojo hint --provider local_openai
dojo campaign create "Improve memory" --planner hermes
```

Generic form:

```bash
dojo --provider hermes admin generate run --topic physics.relativity
dojo --llm-task exercise.generate=local_openai admin generate run
```

But the stable design should prefer task names and roles, not forcing users to think “model” everywhere.

## Provider roles

Useful named roles:

```text
default       fallback for unspecified tasks
extractor     source extraction
writer        exercise/hint generation
grader        free-form scoring
summarizer    learner/profile summaries
planner       campaigns/consolidation
researcher    tool/web-heavy tasks
repair        JSON repair / output normalization
```

Configuration:

```yaml
llm:
  roles:
    default: local_openai
    extractor: local_openai
    writer: hermes
    grader: anthropic
    summarizer: local_openai
    planner: hermes
    researcher: hermes
    repair: local_openai
```

CLI:

```bash
dojo connect role set writer hermes
dojo connect role set grader anthropic
dojo connect role list
```

## Request envelope

Dojo should pass typed request objects to adapters.

```json
{
  "task": "exercise.generate",
  "schema_version": "llm_request.v1",
  "request_id": "llmreq_123",
  "privacy_level": "source_text_allowed",
  "cost_policy": {
    "max_tokens": 4000,
    "max_cost_usd": 0.25,
    "allow_remote": true,
    "prefer_cache": true
  },
  "capability_requirements": {
    "structured_output": true,
    "tools": false,
    "web": false
  },
  "system": {
    "role": "Dojo exercise generator",
    "rules": [
      "Return only JSON matching the schema.",
      "Generate practice, not explanations.",
      "Preserve source provenance."
    ]
  },
  "context_blocks": [
    {
      "type": "task_policy",
      "cache_hint": "stable",
      "content": "..."
    },
    {
      "type": "quality_rubric",
      "cache_hint": "stable",
      "content": "..."
    },
    {
      "type": "learner_profile_summary",
      "cache_hint": "semi_stable",
      "content": "..."
    },
    {
      "type": "source_chunk",
      "cache_hint": "ephemeral",
      "content": "..."
    }
  ],
  "output_schema": {
    "type": "json_schema",
    "schema": {}
  }
}
```

Important: context blocks should be labeled by stability and privacy so adapters can use prompt caching or refuse unsafe calls.

## Response envelope

```json
{
  "ok": true,
  "request_id": "llmreq_123",
  "provider": "hermes",
  "model": "configured-by-harness",
  "task": "exercise.generate",
  "content": {},
  "raw_text": "...",
  "usage": {
    "input_tokens": null,
    "output_tokens": null,
    "cache_read_tokens": null,
    "cache_write_tokens": null,
    "estimated_cost_usd": null
  },
  "provenance": {
    "adapter": "command.v1",
    "command_label": "hermes chat",
    "prompt_version": "exercise.generate.v1",
    "schema_version": "llm_response.v1"
  },
  "warnings": []
}
```

Errors:

```json
{
  "ok": false,
  "request_id": "llmreq_123",
  "provider": "local_openai",
  "error": {
    "code": "structured_output_failed",
    "message": "Provider returned invalid JSON after 2 attempts.",
    "retryable": true
  },
  "fallback_used": "heuristic"
}
```

## System prompt design

Dojo needs reusable prompt layers, not one giant prompt string.

Suggested layers:

1. **Global Dojo contract** — local-first, source-grounded, practice not passive explanation, preserve provenance, no direct durable mutation.
2. **Task contract** — extraction vs generation vs grading vs hinting vs distillation.
3. **Quality rubric** — what counts as useful practice or valid grading.
4. **Output schema** — exact JSON contract.
5. **User/topic context** — compact topic-interest and learner-profile summaries.
6. **Source context** — chunks, excerpts, provenance ids.
7. **Runtime instruction** — specific count, difficulty, constraints.

For harnesses with skill systems, map these layers to reusable skill/context files when possible. For raw APIs, concatenate them with clear headers.

## Prompt caching strategy

Prompt caching should be opportunistic and provider-specific, but Dojo can make it easy by separating stable from ephemeral context.

Stable/cacheable:

- global Dojo contract;
- task instructions;
- output schema;
- quality rubric;
- examples/calibration anchors;
- campaign template;
- stable source document chunks when repeatedly used.

Semi-stable:

- topic-interest profile;
- learner profile summary;
- active campaign plan;
- connector capability docs.

Ephemeral/not worth caching:

- one answer;
- current timestamp;
- session id;
- one-off user correction;
- random small command output.

Design implication:

```json
{
  "context_blocks": [
    {"type": "system_contract", "cache_hint": "stable", "content": "..."},
    {"type": "rubric", "cache_hint": "stable", "content": "..."},
    {"type": "learner_profile", "cache_hint": "semi_stable", "content": "..."},
    {"type": "current_answer", "cache_hint": "ephemeral", "content": "..."}
  ]
}
```

Adapters may ignore cache hints if unsupported. They should record whether caching was used if known.

## Harness integration patterns

### Raw model API pattern

Use when task is bounded and structured:

- extraction from a chunk;
- free-form grading;
- hint generation;
- learner-summary distillation;
- JSON repair.

Pros:

- predictable;
- easier usage/cost accounting;
- fast;
- testable.

Cons:

- no tools unless implemented separately;
- no harness skills/memory;
- weaker for research-heavy or file/project-heavy tasks.

### Command harness pattern

Use when user already has a harness or wants a CLI command to do work.

Examples:

```bash
hermes chat -Q --source dojo --max-turns 8 -q "{prompt}"
claude -p "{prompt}"
codex exec "{prompt}"
opencode run "{prompt}"
my-llm-wrapper --input {input_json_path}
```

Pros:

- supports arbitrary local setups;
- can reuse existing auth/subscriptions;
- can reuse harness skills/tools/memory;
- good for research/generation/campaign planning.

Cons:

- harder to guarantee JSON;
- harder to estimate cost;
- may leak data depending on harness config;
- output may include commentary;
- versioning/reproducibility weaker.

Mitigation:

- use structured request files where possible;
- require adapters to parse/repair/validate output;
- store command label, prompt hash, and adapter version;
- run quality gates before durable state changes.

### Agent harness pattern

Use when task may need tools or multi-step reasoning:

- research-based campaign planning;
- source fetching when connectors are not enough;
- topic consolidation with repo/file inspection;
- complex generation requiring calculations or web context.

Dojo should give the harness a bounded task and schema. The harness returns proposed data; Dojo validates before applying.

### MCP pattern

Future: Dojo may expose its own MCP server and may call external MCP tools through a harness. Keep these separate:

- Dojo-as-MCP-server: agents can call Dojo operations.
- Dojo-using-MCP-tools: a configured harness may access external tools to satisfy a request.

Dojo core should not need to implement a full MCP client for MVP. Harnesses such as Hermes can supply tool access first.

## Structured output and repair

All LLM tasks that affect state should have schemas. If provider lacks native schema support:

1. Prompt for JSON only.
2. Extract JSON from text.
3. Validate schema.
4. Retry once with validation error.
5. Optionally call a `repair` provider.
6. Fail safely.

Do not let invalid or partial output mutate durable state.

## Privacy model

Each task must declare privacy level.

Suggested levels:

```text
no_personal_data        generic prompt/rubric only
learner_summary_only    compact learner profile, no raw answers/source
source_metadata_only    titles/topics/uris, no full text
source_text_allowed     source chunks may be sent
raw_answer_allowed      raw answer may be sent for grading
local_only_required     must not call remote provider
```

Config can restrict by task:

```yaml
privacy:
  default_allow_remote: false
  allow_remote_tasks:
    - exercise.generate
    - answer.grade_freeform
  deny_remote_tasks:
    - learner.distill
  require_local_for_topics:
    - work.private_project
```

CLI overrides should be explicit:

```bash
dojo add private.md --local-only
dojo admin generate run --allow-remote --provider anthropic
dojo doctor --privacy
```

## Cost and budget controls

Dojo should support:

```yaml
llm:
  budgets:
    daily_max_cost_usd: 1.00
    monthly_max_cost_usd: 20.00
    per_task:
      exercise.generate: 0.25
      answer.grade_freeform: 0.05
  caching:
    prefer: true
    stable_prompt_cache: true
```

Commands:

```bash
dojo usage llm
dojo usage llm --today
dojo connect test anthropic --estimate-cost
dojo admin generate run --max-cost 0.25
```

For providers/harnesses without usage reporting, record `unknown` rather than fabricating precision.

## Quality gates

LLM-generated or LLM-graded outputs should pass local gates:

Exercise drafts:

- schema valid;
- target skill clear;
- answer/rubric present;
- difficulty in allowed range;
- source provenance present when source-derived;
- quality evidence above threshold;
- not too toy/generic;
- not duplicate by fingerprint;
- does not silently enter reviewed/trusted queues unless policy permits.

Grades:

- schema valid;
- rubric version present;
- score within range;
- rationale concise;
- confidence present;
- deterministic scorer preferred for exact-answer types.

Hints:

- no final answer leak;
- level appropriate;
- stored as hint event.

Learner insights:

- evidence linked;
- confidence set;
- action proposed or hypothesis updated through explicit service;
- no raw chat overfitting.

## CLI surface for LLM integration

Provider setup:

```bash
dojo connect provider list
dojo connect provider show PROVIDER
dojo connect provider setup PROVIDER
dojo connect provider test PROVIDER
```

Role routing:

```bash
dojo connect role list
dojo connect role set writer hermes
dojo connect role set grader anthropic
dojo connect role set extractor local_openai
```

Task-level override:

```bash
dojo config set llm.tasks.exercise.generate.provider hermes
dojo config set llm.tasks.answer.grade_freeform.provider anthropic
```

Per-command override:

```bash
dojo add notes.md --provider local_openai
dojo admin generate run --provider hermes
dojo answer "..." --grader anthropic
dojo hint --provider local_openai
dojo campaign create "Improve memory" --planner hermes
```

Custom command registration:

```bash
dojo connect provider add-command hermes \
  --command "hermes chat -Q --source dojo --max-turns 8 -q {prompt}" \
  --cap tools,skills,web,system-prompt

dojo connect provider add-command my-llm \
  --command "/usr/local/bin/my-llm --input {input_json_path}" \
  --input file-json \
  --output stdout-json
```

OpenAI-compatible endpoint:

```bash
dojo connect provider add-openai-compatible local \
  --base-url http://localhost:11434/v1 \
  --model qwen2.5:14b \
  --api-key env:DOJO_LOCAL_OPENAI_API_KEY
```

Hosted provider:

```bash
dojo connect provider setup anthropic --api-key env:ANTHROPIC_API_KEY --model claude-sonnet-4
dojo connect provider setup openai --api-key env:OPENAI_API_KEY --model gpt-4.1
```

## Config file sketch

```yaml
llm:
  default_provider: local_openai

  roles:
    default: local_openai
    extractor: local_openai
    writer: hermes
    grader: anthropic
    summarizer: local_openai
    planner: hermes
    researcher: hermes
    repair: local_openai

  tasks:
    source.extract:
      role: extractor
      fallback: heuristic
      privacy_level: source_text_allowed
    exercise.generate:
      role: writer
      fallback: none
      privacy_level: source_text_allowed
    answer.grade_freeform:
      role: grader
      fallback: manual_self_grade
      privacy_level: raw_answer_allowed
    hint.generate:
      role: writer
      fallback: static_hint
      privacy_level: raw_answer_allowed
    learner.distill:
      role: summarizer
      fallback: deterministic_tags_only
      privacy_level: learner_summary_only
    topic.consolidate:
      role: planner
      fallback: deterministic_report
      privacy_level: learner_summary_only
    campaign.plan:
      role: planner
      fallback: guided_questions_only
      privacy_level: learner_summary_only

  providers:
    local_openai:
      type: openai_compatible
      base_url: http://localhost:11434/v1
      model: qwen2.5:14b
      api_key: env:DOJO_LOCAL_OPENAI_API_KEY
      capabilities:
        chat: true
        structured_output: json_schema
        system_prompt: true
        local_only: true

    hermes:
      type: command
      command: hermes
      args: ["chat", "-Q", "--source", "dojo", "--max-turns", "8", "-q", "{prompt}"]
      input_mode: prompt_arg
      output_mode: stdout_text_json_extract
      capabilities:
        chat: true
        structured_output: prompt_only
        tools: true
        web: true
        file_context: true
        skills: true
        system_prompt: true
        can_run_agent_loop: true
      reliability:
        timeout_seconds: 180
        retries: 1

    anthropic:
      type: anthropic
      model: claude-sonnet-4
      api_key: env:ANTHROPIC_API_KEY
      capabilities:
        chat: true
        structured_output: tool_schema
        system_prompt: true
        prompt_cache: true
        streaming: true
```

## Adapter interface sketch

Python protocol concept:

```python
class LLMProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    def complete(self, request: LLMRequest) -> LLMResponse:
        ...
```

Core service:

```python
class LLMRouter:
    def run(self, task: str, payload: dict, *, provider: str | None = None) -> LLMResponse:
        # Resolve task -> role -> provider
        # Check privacy/cost/capabilities
        # Build prompt/request envelope
        # Call adapter
        # Validate/repair structured output
        # Record usage/provenance
        ...
```

## Storage/audit tables

Consider durable audit records for LLM calls that affect state.

```text
llm_requests
  id
  task
  provider
  model
  prompt_version
  schema_version
  privacy_level
  input_hash
  stable_context_hash
  created_at

llm_responses
  id
  request_id
  ok
  output_hash
  usage_json
  cost_estimate
  error_code
  raw_output_path_or_hash
  created_at
```

Do not store raw private source text in audit tables by default. Store hashes and provenance ids; raw output storage should be configurable.

## MVP implementation recommendation

Implement the architecture seam now, not every provider.

MVP should include:

1. `LLMTask` request/response envelopes.
2. Capability declarations.
3. Config-driven provider registry.
4. `openai_compatible` adapter.
5. `command` adapter.
6. Heuristic/no-LLM fallback for source extraction.
7. JSON schema validation/repair loop.
8. Task routing by role.
9. Privacy/cost gates in config, even if basic.
10. CLI commands for provider list/test/role assignment.

Defer:

- full MCP client inside Dojo;
- deep native integrations for every hosted provider;
- complex prompt-cache vendor optimization;
- full agent loop implementation;
- GUI provider setup;
- token-perfect cost accounting for command harnesses.

## Why this design avoids lock-in

- Hermes can be a provider/harness without becoming the product dependency.
- Claude Code/Codex/OpenCode can be configured as command providers.
- OpenAI-compatible local endpoints are first-class.
- Hosted APIs can expose richer structured-output/caching capabilities.
- Future MCP/web/mobile clients call the same Dojo services.
- LLM outputs are proposals/results behind validation gates, not hidden state mutation.

## Example flows

### Use Hermes for exercise generation

```bash
dojo connect provider add-command hermes \
  --command "hermes chat -Q --source dojo --max-turns 8 -q {prompt}" \
  --cap tools,skills,web,system-prompt

dojo connect role set writer hermes
dojo admin generate run --topic physics.relativity --limit 4
```

### Use local OpenAI-compatible endpoint for extraction

```bash
dojo connect provider add-openai-compatible local \
  --base-url http://localhost:11434/v1 \
  --model qwen2.5:14b

dojo connect role set extractor local
dojo add notes.md --topic math.linear_algebra
```

### Use hosted model for free-form grading only

```bash
dojo connect provider setup anthropic --api-key env:ANTHROPIC_API_KEY --model claude-sonnet-4
dojo connect role set grader anthropic
dojo answer "My explanation..."
```

### Force local-only for a private source

```bash
dojo add private-work-note.md --topic work.project_x --local-only
```

If no local provider can satisfy the task, Dojo should fail safely and suggest a deterministic/manual path.
