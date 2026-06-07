# Dojo CLI Interface Design

Status: design baseline
Audience: product/engineering/design
Purpose: define a stable command surface that future Dojo features can target without inheriting prototype-specific names.

## Core stance

Public command: `dojo`
Package/repo name: `dojo` if available, otherwise `cognitive-dojo` for packaging/disambiguation.

Dojo should be a standalone local-first app whose canonical public surface is a CLI plus library API. Telegram/Hermes, MCP, browser, desktop, web, and mobile clients should be adapters over the same core operations.

The CLI should model the product loop:

```text
Add source / goal
  -> extract or create candidates
  -> review / queue practice
  -> start a session
  -> answer / hint / skip / correct
  -> update schedule + learner state
  -> show progress / gaps / atrophy
  -> optionally generate, import, export, sync
```

Everything else is support machinery.

## Design principles

1. **Simple default -> understandable explanation -> optional precise control.**
   - New users should be able to run `dojo add`, `dojo start`, `dojo answer`, `dojo progress`.
   - Power users should be able to inspect topics, policies, learner state, connectors, and provider choices.

2. **Outcome language for public commands.**
   Prefer `start`, `answer`, `hint`, `skip`, `progress`, `source`, `topic`, `campaign`, `profile`, `queue`.

3. **Implementation language goes under `admin` or `internal`.**
   Avoid exposing `upsert`, `policy`, `evidence`, `hypothesis`, `replenish`, `source-bank`, `promote-auto`, `review_state`, or `skill_state` in the normal help surface.

4. **Do not add new top-level commands casually.**
   Bad: `dojo youtube-import`, `dojo readwise-sync`, `dojo taxonomy-cleanup`, `dojo llm-generate`, `dojo anki-export`.
   Good: `dojo source add <youtube-url>`, `dojo connect sync readwise`, `dojo admin topic review`, `dojo admin generate run`, `dojo export anki`.

5. **Adapters call stable internal/library APIs.**
   Hermes/Telegram should call `dojo internal session open` / `dojo internal session reply` or library equivalents, not prototype-era names like `daily-message`.

6. **Every important command supports machine output.**
   Support `--format text|markdown|json` and `--json` as a shortcut.

## Top-level help surface

Default help should show only the practical learner/product surface:

```text
Getting started:
  init        Set up local state
  doctor      Check setup
  demo        Run a sample loop

Practice:
  add         Add a file, URL, text, or goal and prepare practice
  start       Start or resume practice
  ready       Reveal the next prompt
  answer      Answer the current prompt
  hint        Ask for a hint
  skip        Skip current prompt
  correct     Correct the last answer
  resume      Show current session state
  end         End or abandon session
  due         Show what is due

Sources:
  source      Manage sources and candidates
  queue       Queue candidate items for practice

Learning:
  topic       Set priorities and topic settings
  campaign    Focus on a goal over time
  profile     Show learner-model notes
  progress    Short progress summary
  report      Detailed reports

Integrations:
  import      Import from files/tools
  export      Export to files/tools
  connect     Configure connectors and providers
  config      Manage settings

Maintenance:
  usage       Local usage report
  admin       Operator/maintenance commands
  internal    Stable adapter/script commands
```

## Getting started

```bash
dojo init
dojo doctor
dojo demo
```

### `dojo init`

Creates local state.

```bash
dojo init
dojo init --db ~/.local/share/dojo/dojo.sqlite3
dojo init --profile personal
dojo init --with-samples
dojo init --no-samples
```

### `dojo doctor`

Checks local readiness:

- DB exists;
- config valid;
- write permissions;
- optional LLM providers/connectors configured;
- local runtime DBs/secrets are not tracked in repo mode;
- package/version compatibility.

```bash
dojo doctor
dojo doctor --json
dojo doctor --check connectors
dojo doctor --check providers
dojo doctor --privacy
```

### `dojo demo`

Runs a tiny source-to-practice example without requiring Telegram, Hermes, or API keys.

```bash
dojo demo
dojo demo --reset
dojo demo --topic memory
```

## Happy path: `dojo add`

The most important first-run command is:

```bash
dojo add
```

It accepts URL, file, folder, text, or stdin.

```bash
dojo add notes.md --topic physics.relativity
dojo add https://example.com/article --topic chemistry.batteries
dojo add --text "The product rule says..." --title "Product rule note" --topic math.calculus
cat notes.md | dojo add --title "My notes" --topic ml.transformers
```

Default behavior:

1. Create one source record for the whole file/URL/text.
2. Extract one or more topic spans from the source. `--topic` is a hint/default parent topic, not a claim that the whole source has only one topic.
3. Extract candidate practice items, each with its own topic/subtopic and source span/provenance.
4. Keep them as candidates unless policy explicitly allows queueing.
5. Print next recommended actions.

Example output:

```text
Added source: src_abc123
Found 8 candidate practice items.

Next:
  dojo source review src_abc123
  dojo queue --source src_abc123 --limit 3
  dojo start
```

Options:

```bash
dojo add notes.md --topic math.linear_algebra --queue 3
dojo add notes.md --topic math.linear_algebra --start
dojo add notes.md --topic math.linear_algebra --quality reviewed
dojo add notes.md --topic math.linear_algebra --no-generate
dojo add notes.md --topic math.linear_algebra --provider openai
dojo add notes.md --topic math.linear_algebra --local-only
```

Multi-topic source behavior:

```bash
# Hint that the article is broadly about batteries, while allowing finer inferred topics.
dojo add article.md --topic chemistry.batteries --generate

# Let Dojo infer topics without a starting hint.
dojo add article.md --generate
```

A source can contain several topic spans, for example `chemistry.batteries.electrolytes`, `chemistry.batteries.anodes`, and `physics.thermodynamics`. The source record remains one durable object, while candidates point to source spans and carry their own topic paths. Review/queue commands should support filtering by inferred topic:

```bash
dojo source topics src_abc123
dojo source candidates src_abc123 --topic chemistry.batteries.electrolytes
dojo queue --source src_abc123 --topic chemistry.batteries.electrolytes --limit 2
```

`dojo add` is a wrapper over `source`, `queue`, and generation services. It must not become a separate implementation path.

## Source management

Use `source`, not `source-bank`, for public UX.

```bash
dojo source list
dojo source show SOURCE
dojo source add <file|url>
dojo source add --text TEXT --title TITLE
dojo source extract SOURCE
dojo source candidates SOURCE
dojo source review SOURCE
dojo source queue SOURCE
dojo source reject CANDIDATE
dojo source shelve SOURCE
dojo source remove SOURCE
```

Examples:

```bash
dojo source list
dojo source list --topic chemistry.batteries
dojo source show src_abc123
dojo source candidates src_abc123
dojo source review src_abc123
dojo source queue src_abc123 --limit 3
```

Future source types should fit here without new top-level commands:

```bash
dojo source add notes.md
dojo source add ./obsidian-vault/
dojo source add https://example.com/article
dojo source add https://youtube.com/watch?v=...
dojo source add paper.pdf
dojo source add highlights.csv
dojo source add zotero://...
dojo source add readwise:inbox
```

## Queueing practice

The user-facing word for making candidates eligible for practice is `queue`. Internally this may map to `candidate -> promoted exercise`.

```bash
dojo queue --source src_abc123 --limit 3
dojo queue --candidate cand_123
dojo queue --topic chemistry.batteries --limit 5
dojo queue --reviewed-only
dojo queue --auto --topic math.linear_algebra --limit 3
```

Meaning: make selected candidates practiceable.

## Practice/session commands

Dojo's session state machine:

```text
start session
  -> ready reveals prompt and starts timing
  -> answer records response
  -> next prompt waits
  -> hint/skip/correct are structured events
  -> end completes/abandons
```

### `dojo start`

Equivalent to the prototype `daily-message`, but product-shaped.

```bash
dojo start
dojo start --limit 4
dojo start --topic math.arithmetic
dojo start --mode mixed
dojo start --mode review
dojo start --mode new
dojo start --mode maintenance
dojo start --mode calibration
dojo start --mode campaign
dojo start --new
dojo start --reset
dojo start --batch
dojo start --channel telegram
dojo start --format markdown
dojo start --json
```

Default:

- reuse today's open session if appropriate;
- ready-gated progressive mode;
- no prompt reveal until `dojo ready`;
- human-friendly output.

Potential `--mode` values:

```text
mixed         reviews + weak + source + maintenance
review        due review only
new           mostly new queued material
source        source-derived practice
maintenance   atrophy/staleness checks
calibration   estimate level in a topic
campaign      campaign-specific session
weak          target weak topics
```

### `dojo ready`

Reveal next prompt and start timing.

```bash
dojo ready
dojo ready --session sess_123
dojo ready --channel telegram
```

### `dojo answer`

`dojo answer` means answer the current active session prompt.

```bash
dojo answer "142"
dojo answer "dx=-2 dy=1 facing=north"
dojo answer --file answer.txt
dojo answer --received-at 2026-06-06T12:34:00Z
dojo answer --session sess_123 "142"
dojo answer --json "142"
```

Batch answers:

```bash
dojo answer --batch-file answers.txt
dojo answer $'1. 142\n2. dx=-2 dy=1 facing=north'
```

### `dojo answer` vs `dojo admin attempt record`

These are intentionally different.

`dojo answer` is a **session interaction**:

- answers the currently revealed prompt or a specific item in an active session;
- uses session state to know which exercise is being answered;
- captures interaction events such as `answer_received`;
- derives timing from `prompt_revealed -> answer_received` when possible;
- applies normal scoring;
- advances/checkpoints the session;
- is what Telegram, desktop, mobile, and normal CLI users should call.

`dojo admin attempt record` is a **low-level data operation**:

- records an attempt for an explicit exercise, usually outside the normal session flow;
- requires fields that a normal user should not have to supply, such as exercise id, response, seconds, rating, hint count, and sometimes scoring override;
- is for imports, repairs, backfills, tests, migrations, and operator fixes;
- should not reveal prompts, advance sessions, or pretend to know conversational context;
- may update review/skill state, but does not represent a full user interaction unless explicitly linked to a session/item.

In short:

```text
answer = "I am practicing right now; record my reply to the current prompt."
admin attempt record = "Write this attempt event into the database for this known exercise."
```

This split prevents accidental data corruption. Normal clients should not need exercise ids; admin tools should not infer user-session context.

### `dojo hint`

```bash
dojo hint
dojo hint --another
dojo hint --level 1
dojo hint --session sess_123
```

Records structured hint events.

### `dojo skip`

```bash
dojo skip
dojo skip --reason too-hard
dojo skip --reason too-easy
dojo skip --reason too-known
dojo skip --reason bad-prompt
dojo skip --reason not-interested
dojo skip --reason not-now
```

### `dojo correct`

```bash
dojo correct "dx=-7 dy=-3 facing=west"
dojo correct --item 4 "dx=-7 dy=-3 facing=west"
dojo correct --last "142"
```

Corrections become structured events rather than informal chat conventions.

### `dojo resume`

```bash
dojo resume
dojo resume --session sess_123
dojo resume --channel telegram
```

Shows current open session, current item, whether waiting for ready/answer, and remaining count.

### `dojo end`

```bash
dojo end
dojo end --complete
dojo end --abandon
dojo end --session sess_123
```

## Due/progress/report

Separate three levels:

```text
due       what can be practiced now
progress  short practical summary
report    richer drill-down reports
```

```bash
dojo due
dojo due --limit 10
dojo due --topic memory
dojo due --json
```

```bash
dojo progress
dojo progress --by topic
dojo progress --by skill
dojo progress --recent 20
dojo progress memory
dojo progress --json
```

```bash
dojo report retention
dojo report atrophy
dojo report weak
dojo report sources
dojo report topics
dojo report schedule
dojo report weekly
dojo report usage
dojo report calibration
```

Reports should power future dashboards through JSON output.

## Topic/category management

Use `topic`, not `category`, for public UX.

```bash
dojo topic list
dojo topic show TOPIC
dojo topic set TOPIC --priority low|normal|high
dojo topic set TOPIC --mode explore|balanced|maintenance|mastery
dojo topic set TOPIC --min-quality experimental|reviewed|trusted
dojo topic review
dojo topic rename OLD NEW
dojo topic merge OLD NEW
dojo topic shelve TOPIC
```

Examples:

```bash
dojo topic list
dojo topic show math.linear_algebra
dojo topic set chemistry.batteries --priority high
dojo topic set math.arithmetic --mode maintenance
dojo topic review
```

Advanced policy remains under admin:

```bash
dojo admin topic policy set math.arithmetic \
  --goal-type maintenance \
  --target-mastery 0.85 \
  --new-weight 0.2 \
  --review-weight 1.0 \
  --min-quality reviewed
```

## Campaigns

A campaign has a goal, scope, calibration, cadence, target duration, diagnostic ladder, sources, practice mix, and success criteria.

```bash
dojo campaign list
dojo campaign create NAME
dojo campaign show CAMPAIGN
dojo campaign start CAMPAIGN
dojo campaign pause CAMPAIGN
dojo campaign end CAMPAIGN
dojo campaign calibrate CAMPAIGN
dojo campaign add-source CAMPAIGN SOURCE
dojo campaign report CAMPAIGN
```

Examples:

```bash
dojo campaign create "Linear algebra foundations" \
  --topic math.linear_algebra \
  --goal "Understand matrices geometrically and computationally" \
  --weeks 4

dojo campaign calibrate camp_123
dojo start --campaign camp_123
dojo campaign report camp_123
```

Vague goals should trigger calibration/interview rather than immediate hard generated content:

```bash
dojo campaign create "Improve memory" --guided
```

## Learner profile

Public:

```bash
dojo profile show
dojo profile show TOPIC
dojo profile note TOPIC TEXT
```

Examples:

```bash
dojo profile show math.calculus
dojo profile note math.calculus "I mix up product rule and chain rule."
```

The system decides whether that note becomes evidence, hypothesis, preference, or campaign context.

## Import/export

`dojo add` handles the common case. `dojo import` and `dojo export` handle explicit formats/tools.

```bash
dojo import markdown notes.md --topic physics.relativity
dojo import folder ./notes --topic work.project_x
dojo import anki deck.apkg
dojo import csv cards.csv --format quizlet
dojo import kindle "My Clippings.txt"
dojo import pocket pocket-export.csv
dojo import omnivore omnivore-export.json
dojo import zotero library.bib
dojo import rss https://example.com/feed.xml
```

```bash
dojo export anki --topic chemistry.batteries --out batteries.apkg
dojo export csv --topic math.arithmetic --out arithmetic.csv
dojo export json --out dojo-export.json
dojo export markdown --topic physics.relativity --out practice.md
dojo export report weekly --out weekly.md
```

## Connectors and providers

Use `connect` for integrations and provider setup.

```bash
dojo connect list
dojo connect show CONNECTOR
dojo connect setup CONNECTOR
dojo connect test CONNECTOR
dojo connect sync CONNECTOR
```

Examples:

```bash
dojo connect setup obsidian --path ~/Vault
dojo connect sync obsidian

dojo connect setup telegram
dojo connect setup ollama --base-url http://localhost:11434
dojo connect setup openai --api-key env:OPENAI_API_KEY
dojo connect test openai
```

For LLM/provider design, see `docs/llm-provider-interface.md`.

## Config

```bash
dojo config get
dojo config get db.path
dojo config set default_provider ollama
dojo config set practice.default_limit 4
dojo config set privacy.telemetry false
dojo config path
```

Learner/topic preferences should use `dojo topic`, not generic config.

## Privacy and usage

```bash
dojo usage
dojo usage --json
dojo usage --share
dojo usage --share --dry-run
```

Default: print local aggregate counters only. No sharing silently.

## Admin namespace

Powerful/operator/internal concepts go under `admin`.

```bash
dojo admin content seed
dojo admin content status
dojo admin content needs
dojo admin content promote --auto

dojo admin generate run
dojo admin generate import-drafts
dojo admin generate log

dojo admin topic review
dojo admin topic policy list
dojo admin topic policy set

dojo admin learner evidence add
dojo admin learner hypothesis set
dojo admin learner hypothesis status

dojo admin attempt record
dojo admin attempt rescore
dojo admin attempt replay

dojo admin feedback exercise
dojo admin prospective check
dojo admin repair
dojo admin debug
```

## Internal namespace

Hidden from ordinary help. Stable for adapters/scripts.

```bash
dojo internal session open
dojo internal session reveal
dojo internal session reply
dojo internal session state
dojo internal prospective check
dojo internal report render
dojo internal connector sync
```

Examples:

```bash
dojo internal session open --channel telegram --format markdown
dojo internal session reply --channel telegram --text "$TEXT" --received-at "$TS" --format markdown
dojo internal session reveal --channel telegram --format markdown
```

## Output format and JSON contract

Every important command supports:

```bash
--format text|markdown|json
--json
```

Suggested JSON success shape:

```json
{
  "ok": true,
  "type": "practice_session_started",
  "data": {},
  "warnings": [],
  "next_actions": []
}
```

Suggested JSON error shape:

```json
{
  "ok": false,
  "error": {
    "code": "no_open_session",
    "message": "No open session found.",
    "next_actions": ["dojo start"]
  }
}
```

Human output may change. JSON output should be stable enough for tests, adapters, MCP, and future apps.

## Legacy migration map from prototype

```text
init                         -> init
seed                         -> admin content seed
due                          -> due
daily-message                -> start / internal session open
reply                        -> answer / ready / internal session reply
answer --exercise-id ...      -> admin attempt record
status                       -> status
progress-report              -> progress
memory-status                -> progress memory
check-prospective            -> admin prospective check / internal prospective check
source-bank add              -> source add --candidate ...
source-bank import-text       -> source add <file|--text> / import markdown/text
source-bank import-url        -> source add <url>
source-bank replenish-text    -> add/source add + queue, or admin content equivalent
source-bank list             -> source candidates / source list --candidates
source-bank promote          -> queue / source queue
source-bank promote-auto      -> admin content promote --auto
source-bank needs-replenishment -> admin content needs
llm-replenish                -> admin generate import-drafts
auto-replenish               -> admin generate run
replenishment-log            -> admin generate log
exercise-feedback            -> admin feedback exercise
category-review              -> topic review / admin topic review
category-preference set/list  -> topic set/list
category-policy set/list      -> admin topic policy set/list
bank-status                  -> report sources / admin content status
learner-profile show          -> profile show
learner-profile record-evidence -> admin learner evidence add
learner-profile upsert-hypothesis -> admin learner hypothesis set
learner-profile set-status   -> admin learner hypothesis status
```

## MVP command slice

Implement first:

```bash
dojo init
dojo doctor
dojo demo

dojo add
dojo source list
dojo source show
dojo source candidates
dojo queue

dojo start
dojo ready
dojo answer
dojo resume
dojo end
dojo due

dojo progress
dojo report retention

dojo topic list
dojo topic set

dojo export anki
dojo export json

dojo usage
```

Admin/internal MVP:

```bash
dojo admin content seed
dojo admin content status
dojo admin generate run
dojo admin generate log
dojo admin attempt record

dojo internal session open
dojo internal session reply
```
