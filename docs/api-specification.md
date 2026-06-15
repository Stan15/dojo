# Dojo API & Command Specification

This document provides the authoritative technical reference for the implemented Dojo programmatic Python API (`DojoAPI`), the CLI command-line interface, and key architectural nuances.

---

## 1. Programmatic API (`DojoAPI`)

The programmatic Python API is defined in [`src/dojo/api.py`](file:///Users/stans/projects/dojo/src/dojo/api.py) and is the single source of truth for business logic.

### Initialization
```python
from dojo.api import DojoAPI
api = DojoAPI(db_path=None)
```
*   `db_path`: Absolute path to the SQLite database. If omitted, defaults to `~/.local/share/dojo/dojo.sqlite3`. Initializes/migrates tables automatically.

### Source & Candidate Methods

*   `add_source(title, content, kind, path=None, mission=None, generate_candidates=False, topic=None) -> dict`
    *   Saves a raw text/file/URL source.
    *   If `generate_candidates=True`, invokes the default AI connector with task `exercise.generate` to draft exercises.
*   `list_sources() -> list[dict]`
    *   Returns meta-information for all ingested sources, including draft candidate counts.
*   `get_source(source_id) -> dict | None`
    *   Retrieves source metadata and content.
*   `get_source_topics(source_id) -> list[dict]`
    *   Lists all unique topics and candidate counts drafted from a source.
*   `get_source_candidates(source_id, topic_path=None) -> list[dict]`
    *   Lists draft candidate exercises for a source, optionally filtered by topic.
*   `get_candidate(candidate_id) -> dict | None`
    *   Retrieves a single candidate's details.
*   `save_candidate(id, source_id, prompt, answer=None, rubric=None, topic_path, source_refs, difficulty=None, quality="candidate") -> dict`
    *   Upserts or modifies a candidate exercise draft.
*   `remove_candidate(candidate_id) -> dict`
    *   Permanently deletes a draft candidate from the database.

### Queueing & Promotion

*   `promote_candidate(candidate_id) -> dict`
    *   Deletes the candidate draft and promotes it to an active `Exercise`.
    *   Enforces the active queue limit (max 20). Raises `ValueError` if the limit is exceeded.
*   `promote_source_topic(source_id, topic_path=None, limit=None) -> list[dict]`
    *   Promotes multiple candidates from a source/topic. Enforces the active queue limit per item.

### Practice Session Lifecycle

*   `start_practice_session(topic=None, limit=5, reset=False) -> dict`
    *   Starts a session of up to `limit` active exercises. Resumes the active session by default unless `reset=True`.
    *   **JIT Replenishment:** If the due exercise queue falls below 3 items, it automatically triggers candidate generation from active sources and promotes them.
*   `get_active_practice_session() -> dict | None`
    *   Retrieves the current active session.
*   `reveal_prompt(session_id=None) -> dict`
    *   Reveals the prompt of the active exercise in the session and starts the response timer.
*   `submit_answer(user_answer, session_id=None) -> dict`
    *   Submits the response, records the attempt score and latency, and increments the session index.

### Skip & Correct Feedback Loop

*   `get_due_count(topic=None) -> int`
    *   Queries active unattempted exercises (including exercises where the only attempts are skips with reason `"forgot"`).
*   `skip_active_exercise(reason, feedback=None, session_id=None) -> dict`
    *   Skips the active exercise with a reason (`forgot`, `too_easy`, `too_hard`, `bad_quality`) and optional notes.
    *   If `"forgot"`, the exercise remains due in rotation. For other reasons, it is archived.
*   `correct_last_attempt(feedback=None, session_id=None) -> dict`
    *   Overrides the last recorded attempt score in the session (or globally) to `1.0` (correct).

### Learner Profile Consolidation

*   `get_learner_hypotheses(status="active") -> list[dict]`
    *   Lists consolidated learner hypotheses (misconceptions/patterns).
*   `save_learner_hypothesis(key, description, status="active") -> dict`
    *   Upserts a hypothesis key-description record.
*   `consolidate_learner_profile() -> dict`
    *   Synthesizes the last 20 attempts using the default AI connector (`profile.consolidate`).
    *   Outdated active hypotheses not returned by the connector are set to `"resolved"`.

---

## 2. CLI Command Specification

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `dojo add` | `<path> [--text <txt>] [--title <t>] [--generate]` | Ingests a text source/file/URL. |
| `dojo source list` | None | Lists ingested sources and candidate counts. |
| `dojo source show` | `<source-id>` | Shows source metadata and content snippet. |
| `dojo source topics` | `<source-id>` | Lists draft topics for a source. |
| `dojo source candidates` | `<source-id> [--topic <path>]` | Lists candidate details for a source/topic. |
| `dojo source review` | `<source-id>` | Interactive terminal review of candidates. |
| `dojo queue` | `<candidate-id> | --source <id> [--limit <n>]` | Promotes candidate(s) to active exercises. |
| `dojo start` | `[--topic <path>] [--limit <n>] [--reset]` | Starts/resumes a session (triggers JIT if due queue < 3). |
| `dojo ready` | `[--session <id>]` | Reveals the prompt and starts the timer. |
| `dojo answer` | `<answer> [--session <id>]` | Submits response and scores correctness. |
| `dojo due` | `[--topic <path>]` | Returns the count of active due exercises. |
| `dojo skip` | `--reason <reason> [--feedback <txt>]` | Skips exercise (`forgot` keeps due; others archive). |
| `dojo correct` | `[--feedback <txt>]` | Overrides the score of the last attempt to `1.0`. |
| `dojo progress` | None | Lists accuracy, latency, and recent attempts. |
| `dojo admin consolidate` | None | Periodically synthesizes stable hypotheses from attempts. |
| `dojo install` | `<hermes | openclaw>` | Installs skill and auto-configures default AI connector. |
| `dojo connect ai command` | `<name> -- argv` | Registers a command-based AI connector. |
| `dojo connect ai list` | None | Lists registered AI connectors. |
| `dojo connect ai test` | `[<name>]` | Tests AI connector connectivity. |

---

## 3. Structural Nuances

### The Dual Purpose of Sources
Sources serve two distinct dual purposes in Dojo:

#### A. Content-Type: Factual Reference vs. Structured Learning Plan
Depending on the content ingested, a `Source` behaves as factual target material or a roadmap syllabus. We resolve the tension between these two modes by recognizing that **every structured reference document is also a syllabus via its outline hierarchy** (see [ADR 001](file:///Users/stans/projects/dojo/docs/adr/001-unified-source-representation.md) for details):
1.  **Factual Reference Material:** Contains target raw text, articles, papers, codebases, or reference notes. Dojo uses these to extract specific factual items, QA pairs, or procedural practice prompts.
2.  **Learning Plan / Syllabus:** Contains a structured study roadmap, curriculum outline, course syllabus, or list of learning milestones. When ingested, this acts as the outline for a `Campaign`, which coordinates the progression sequence, active phase, and pedagogical strategy profile parameters to direct JIT generation (see [ADR 002](file:///Users/stans/projects/dojo/docs/adr/002-campaign-as-pedagogical-director.md) for details).

#### B. Execution-Type: Generative Input vs. Provenance Trace
During the practice loop, a source acts as:
1.  **Generative Input:** Serves as the raw contextual prompt input fed into the default AI connector during draft generation.
2.  **Provenance Anchor:** Grounds promoted exercises. The `source_refs` map exercises back to their exact line numbers or positions in the original source, allowing the learner to review context, verify grading correctness, and resolve active learner hypotheses.

### The "Forgot" Skip Exception
*   **Volatile Skips:** Skips with reasons `"too_easy"`, `"too_hard"`, or `"bad_quality"` indicate curriculum calibration issues. The exercise quality is immediately set to the skip reason, archiving the item out of active rotation.
*   **Desirable Difficulty Skips:** Skips with reason `"forgot"` represent a retrieval failure. The exercise remains active and **due** in rotation so the learner re-encounters it in future sessions.

### Active Queue Guardrail
*   Dojo enforces a strict cap of **20 active due exercises** at any given time.
*   If the due count is $\ge 20$, promotion via reviews or queue commands is blocked. This prevents cognitive overload and bombardment, forcing the learner to practice due items before adding more material.
