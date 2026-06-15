---
name: dojo
description: Guidance on using the Dojo Learning System CLI to ingest notes, manage candidate exercises, and run practice recall sessions.
---

# Dojo Learning System Skill

This skill allows the agent to interact with the Dojo Learning System CLI, enabling it to ingest notes, manage exercises, and run study sessions.

## Overview of CLI Commands

All commands support the `--json` flag to return structured JSON envelopes, and should be run with `--json` in agent/non-interactive environments.

### 1. Ingesting Sources & Generating Candidates
To add a text source and automatically generate practice candidates:
```bash
dojo add --text "Calculus notes here." --title "Calculus" --topic "math.calculus" --mission "Learn derivatives" --generate
```
*   `--generate`: Triggers exercise candidate drafting via the configured AI connector.
*   Outputs a JSON object containing the `source_id` (e.g., `src_abcdef12`).

### 2. Inspecting Candidates
*   **List Topics:** List inferred topics and candidate counts for a source:
    ```bash
    dojo source topics <source-id>
    ```
*   **List Candidates:** List all candidate drafts for a source, optionally filtered by topic:
    ```bash
    dojo source candidates <source-id> [--topic <topic>]
    ```

### 3. Queueing/Promoting Candidates
*   **Bulk Queue:** Promote candidate drafts matching a topic from a source to active exercises:
    ```bash
    dojo queue --source <source-id> [--topic <topic>] [--limit <limit>]
    ```
*   **Queue by ID:** Promote a single candidate to active exercise:
    ```bash
    dojo queue <candidate-id>
    ```

### 4. Running Practice Sessions
*   **Start Session:** Open or resume a practice session (returns `session_id`). If the due queue has fewer than 3 exercises, it automatically generates 3–5 new items from active sources using the default AI connector:
    ```bash
    dojo start [--topic <topic>] [--limit <limit>]
    ```
*   **Reveal Prompt:** Get the active prompt and start the timer (run with `--json` or `--no-input` to avoid TTY block):
    ```bash
    dojo ready [--session <session-id>]
    ```
*   **Answer Prompt:** Submit the answer to the active prompt. Calculates latency and evaluates correctness:
    ```bash
    dojo answer <user-answer> [--session <session-id>]
    ```
*   **Progress Dashboard:** List recall latency, accuracy, and recent attempts:
    ```bash
    dojo progress
    ```

### 5. Managing Queue & Feedback
*   **Check Due Count:** Query the number of active unattempted exercises:
    ```bash
    dojo due [--topic <topic>]
    ```
*   **Skip Exercise:** Skip the active exercise in a session with a specific reason and optional feedback text:
    ```bash
    dojo skip --reason <forgot|too_easy|too_hard|bad_quality> [--feedback <feedback>] [--session <session-id>]
    ```
    *   *Forgot:* Keeps the exercise in rotation (remains due/active).
    *   *Too Easy / Too Hard / Bad Quality:* Archives the exercise dynamically (removes from active queue).
*   **Correct Attempt:** Override a rigid grader mistake on the last attempt to `1.0` (correct) with optional explanation notes:
    ```bash
    dojo correct [--feedback <notes>] [--session <session-id>]
    ```

### 6. Learner Profile Consolidation & Preferences (Admin)
*   **Consolidate Hypotheses:** Periodically consolidate recent attempts, skips, and free-form feedback into stable learner profile hypotheses:
    ```bash
    dojo admin consolidate
    ```
    *   Invokes the default AI connector internally with the task `profile.consolidate` to analyze the last 20 attempts.
    *   Upserts active misconceptions and resolves outdated hypotheses.
    *   Active hypotheses are automatically injected into future JIT generation runs to calibrate difficulty and target weak areas.
*   **Manage Preferences (Config):** View and set configuration preferences:
    ```bash
    dojo config show
    dojo config set <key> <value>
    ```
    *   Common keys: `schedule.enabled` (`"true"`/`"false"`), `schedule.daily_time_utc` (`"HH:MM"`).

## Curator / Integration Guidelines
1.  **Agent-Delegated Daily Scheduling:**
    *   At startup or on change, the agent MUST inspect the configurations using `dojo config show --json`.
    *   If `schedule.enabled` is `"true"` and `schedule.daily_time_utc` is set, the agent framework must register a recurring daily background task.
    *   When the timer fires, the agent initiates the daily study reminder and starts the practice session conversationally.
2.  **Handling Diagnostic Questions:**
    *   If JIT candidate generation returns diagnostic/pedagogical questions (indicated by `"quality": "diagnostic"`), Dojo serves them during the practice session.
    *   The agent should converse naturally to get the user's response to the diagnostic question, then submit the answer via `dojo answer "<response>"`.
    *   These responses are later consolidated by `dojo admin consolidate` into stable, calibrating hypotheses.
3.  **Avoid Volatile Adjustments:** Do not attempt to alter lesson campaigns directly on every single user comment. Instead, rely on `dojo skip` and `dojo correct` to log raw feedback, and trigger `dojo admin consolidate` periodically (e.g., at the end of a session or when requested) to synthesize stable hypotheses.
4.  **JIT Replenishment:** Rely on `dojo start`'s automatic JIT replenishment logic to generate new practice items on demand, preventing excess advance generation and maintaining adaptive flexibility.

