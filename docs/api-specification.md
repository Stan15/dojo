# Dojo CLI & API Reference

_Rewritten 2026-07-08 against the shipped surface (M6 truth pass). Design
rationale lives in [`design/blueprint.md`](design/blueprint.md); this documents
what exists. Every command supports `--json` (structured envelopes) and
`--db <dir>` (store location, default `~/.local/share/dojo`)._

## The envelope protocol

Every JSON response may carry:

- `tasks: [{id, kind, prompt_file, submit_with, payload_bytes}]` — AI work for
  the driving agent (or `dojo task run`) to fulfill NOW. This is the only way
  AI touches dojo: read the prompt, produce the JSON it demands, submit it;
  the result is schema-validated and applied atomically (ADR 010, I5).
- `next` — one plain-language sentence naming the next step.
- Honest degradation counts where relevant: `skipped`, `generation_deferred`,
  `inbox_waiting`, `pending_grade`.

## Commands

### Learning goals & material

| Command | What it does |
|---|---|
| `dojo campaign plan "<goal>" [--level] [--context]` | Emits a `campaign.plan` task: mission, lean topic tree, phases, refinement questions. Vague goals get calibration-first plans + elucidating questions. |
| `dojo campaign create --from-task <tsk-id> [--name]` | Materializes a fulfilled plan proposal — nothing is created before your approval (I2). |
| `dojo campaign create "<goal>" [--level] [--source]` | Deterministic creation with a diagnostic phase (no AI plan). |
| `dojo add <path|--text> [--topic] [--generate]` | Ingests a source; `--generate` emits a grounded generation task. |
| `dojo capture "<text>" [--why]` | Saves a micro-source durably BEFORE any AI runs, then emits a `capture.route` task. |
| `dojo inbox [confirm|dismiss <cap-id>]` | Captures awaiting a home; routes are proposals until you confirm (Q6; `capture.autofile` config opts into auto-filing high-confidence routes). |
| `dojo source list|show|topics|candidates|review` | Inspect sources; review gates AI-drafted candidates. |
| `dojo queue <candidate-id> | --source <id>` | Promotes reviewed candidates to active practice (queue caps enforced). |

### Daily practice

| Command | What it does |
|---|---|
| `dojo daily [--size N] [--reset]` | Builds today's packet: bounded (default 5, hard cap 8), interleaved across campaigns, every pick explained. Cold campaigns get ONE diagnostic task first; stock requests are phase-gated and capped at 2 AI tasks per run. Resumes within the day. |
| `dojo why` | Replays every scheduling reason behind the current packet, including Tier-1 campaign ranking and your boosts. |
| `dojo ready` / `dojo answer "<answer>"` | Reveal prompt (timer starts) / submit. Exact matches and diagnostics grade deterministically; rubric-bearing answers emit an `attempt.grade` task (`pending_grade: true`). |
| `dojo skip --reason too_easy|too_hard|forgot|bad_quality [--feedback]` | Calibration signals. `forgot` keeps the item due (Again); `too_easy` archives with an Easy review; `too_hard`/`bad_quality` archive. |
| `dojo correct [--score] [--feedback]` | Human override of the last grade (highest authority; lands as an additional review — OP #13). |
| `dojo feedback "<comment>"` | Free-text learning feedback, consumed by reflection. |
| `dojo campaign boost <id> <factor>` | This CAMPAIGN surfaces more/less in daily packets (Tier-1 multiplier, visible in `why`). |
| `dojo campaign topic-boost <id> <path> <factor> [--kind]` | This TOPIC comes due `<factor>`× faster and wins packet ties. |
| `dojo start|reveal|due|progress` | Session utilities predating `daily`; `start` also replenishes when a topic runs low. |

### Understanding & upkeep

| Command | What it does |
|---|---|
| `dojo stats` | Estimated retention per campaign (tagged estimate), due counts, 20-attempt accuracy, idle days, insights, and AI token spend per task kind. |
| `dojo reflect [--campaign]` | Emits `campaign.reflect` over unreflected evidence → insights (created/updated/resolved under mechanical rails), strategy calibration, rare plan revisions, journal. No new evidence → honest no-op. |
| `dojo task list|show [--prompt]|submit|run` | The task queue. `run` drains pending tasks through one configured command string (`fulfiller.command`) — prompt on stdin, JSON on stdout. |
| `dojo benchmark --driver "<cmd>" [--judge] [--tier] [--detail]` | Scores a (driver, judge) model pair on the shipped pedagogy corpus by category, with measured token economy. Runs in throwaway stores — never touches yours. |
| `dojo export <dir>` | Writes your entire store as a fresh markdown store, read through the storage protocol (backend-blind). Refuses non-empty destinations. |
| `dojo doctor` | Validates store structure, schemas, task queue, inbox, and audit health. |
| `dojo config set|show` | Key-value config: `daily.packet_size`, `fulfiller.command`, `fulfiller.tier` (frugal/standard/rich context budgets), `capture.autofile`. |
| `dojo install [<agent>|--dest] [--argv]` / `dojo uninstall [<agent>|--dest|--self]` | Skill install into an agent's directory / removal (ownership-guarded; learning data never touched). |

## Local fulfiller driver guidance

Configuring `fulfiller.command` or `dojo benchmark --driver` against a local
ollama model? Three rulings from the token-diet measurement campaign
(2026-07-18; full evidence in `scratch/token-diet/REPORT.md` and
`WORKBENCH.md`):

- **Do not pipe `ollama run` on ollama ≥0.32.** The CLI writes its terminal
  word-rewrap rendering into non-TTY stdout — ANSI erase sequences,
  re-printed word fragments, even doubled closing quotes — landing inside
  JSON string values and corrupting the payload. Short responses don't wrap
  so a quick smoke test can look clean while a real battery comes back
  0/64 on "no JSON found." `TERM=dumb` does not help. Drive the model
  through the HTTP API instead (`POST /api/chat`, `stream: false`);
  `scratch/token-diet/api_driver.py` is the reference implementation.
- **Disable thinking for thinking-class models (qwen3.5 etc.).** Left on,
  a trivial one-field JSON task took 121-164s and up to 17.7KB of
  rumination; with thinking off, 1-2s. Set `"think": false` in the
  `/api/chat` request body — this is the only endpoint where the flag
  binds. `/api/generate` with `think: false` still emits full reasoning
  (verified on qwen3:4b). Old (non-.5) qwen3 needs a model-specific
  soft-switch instead of the `think` field; that variant is not yet
  supported and is deferred.
- **Best-in-class local models as of 2026-07:** `qwen3.5:0.8b` (~1GB tier)
  and `qwen3.5:4b` (~3.4GB tier). Benchmark calibers are the strongest
  model per resource class, not an arbitrary same-footprint pick, so a
  local scorecard reflects the floor a real user on that hardware actually
  gets (`docs/STATE.md` standing directive).

## Python API

`dojo.api.DojoAPI(dojo_dir=None)` mirrors the CLI: `daily()`, `why()`,
`capture()`, `inbox()/inbox_confirm()/inbox_dismiss()`, `stats()`,
`add_source()`, `start_practice_session()`, `reveal_prompt()`,
`submit_answer()`, `skip_active_exercise()`, `correct_last_attempt()`,
`consolidate_learner_profile()`, `create_campaign()`. Storage is the `DojoStore`
protocol (`dojo.store`) — typed repositories per entity, ID references only
(ADR 011); `dojo.export.export_store(src, dest)` is the portability path.

## Storage layout (markdown backend)

```
~/.local/share/dojo/
  config.yaml
  inbox/cap_*.md                 # captures (body = the note)
  sources/src_*.md               # provenance in frontmatter, content as body
  tasks/tsk_*.md                 # task prompts as bodies; status/errors in frontmatter
  campaigns/camp_<id>/
    campaign.md                  # mission/strategy/topics(+sr)/journal; syllabus as body
    plan.yaml
    exercises/ candidates/ attempts/ insights/
  archive/                       # archived campaigns & sessions
```

Everything is git-versioned with one recovery point per CLI command; the log
reads as a narrative of your learning life.
